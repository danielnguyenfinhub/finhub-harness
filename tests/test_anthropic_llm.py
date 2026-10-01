"""Slice 4 adapter proof tests. Offline: the SDK talks to httpx2.MockTransport only.

The key below is a dummy that exists only in this file; no real key is read or used.
"""

from __future__ import annotations

import json
import logging
import re
import site
import time
import traceback
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from master_finhub.runtime import anthropic_llm
from master_finhub.runtime.anthropic_llm import (
    CONNECT_TIMEOUT_S,
    LOGGER_NAMES,
    READ_TIMEOUT_S,
    RETRY_AFTER_CAP_S,
    AnthropicLLM,
    ProviderError,
    from_anthropic_message,
    to_anthropic_messages,
    to_anthropic_tools,
)
from master_finhub.runtime.loop import AgentLoop, Message, ToolCall, ToolSpec
from master_finhub.tools.builtins.echo import EchoTool

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")

DUMMY_KEY = "sk-ant-test-DUMMY"
PROMPT_SENTINEL = "CLIENT_A_PROMPT_SENTINEL"
Handler = Callable[[Any], Any]


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ANTHROPIC_API_KEY", DUMMY_KEY)
    for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_LOG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(time, "sleep", lambda _s: None)  # never really sleep
    saved = {n: logging.getLogger(n).level for n in LOGGER_NAMES}
    yield
    for name, level in saved.items():
        logging.getLogger(name).setLevel(level)


def reply(
    blocks: list[dict[str, Any]], stop: str | None = "end_turn", **extra: Any
) -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "m",
        "content": blocks,
        "stop_reason": stop,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
        **extra,
    }


def text(t: str) -> dict[str, Any]:
    return {"type": "text", "text": t}


def tool_use(i: str = "toolu_1", text_arg: str = "hi") -> dict[str, Any]:
    return {"type": "tool_use", "id": i, "name": "echo", "input": {"text": text_arg}}


def sdk_message(blocks: list[dict[str, Any]], stop: str | None = "end_turn", **extra: Any) -> Any:
    return anthropic.types.Message.model_validate(reply(blocks, stop, **extra))


def make(handler: Handler, **kwargs: Any) -> AnthropicLLM:
    return AnthropicLLM("m", transport=httpx2.MockTransport(handler), **kwargs)


def ok(blocks: list[dict[str, Any]] | None = None, stop: str = "end_turn") -> Handler:
    return lambda request: httpx2.Response(200, json=reply(blocks or [text("done")], stop))


def status(code: int, body: dict[str, Any] | None = None, **headers: str) -> Handler:
    return lambda request: httpx2.Response(code, json=body or {}, headers=headers)


USER_HI = [Message("user", "hi")]


# --- translation (pure) -----------------------------------------------------------------


def test_user_text_becomes_user_block() -> None:
    assert to_anthropic_messages([Message("user", "hi")]) == [
        {"role": "user", "content": [{"type": "text", "text": "hi"}]}
    ]


def history() -> list[Message]:
    calls = (ToolCall("c1", "echo", {"text": "a"}), ToolCall("c2", "echo", {"text": "b"}))
    return [
        Message("user", "go"),
        Message("assistant", "ok", tool_calls=calls),
        Message("tool", "a", tool_call_id="c1"),
        Message("tool", "b", tool_call_id="c2"),
    ]


def test_parallel_tool_results_merged_in_order() -> None:
    out = to_anthropic_messages(history())
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert [b["tool_use_id"] for b in out[2]["content"]] == ["c1", "c2"]  # type: ignore[typeddict-item]


def test_assistant_tool_calls_become_tool_use_blocks() -> None:
    blocks = to_anthropic_messages(history())[1]["content"]
    assert blocks[0] == {"type": "text", "text": "ok"}  # type: ignore[index]
    assert blocks[1] == {  # type: ignore[index]
        "type": "tool_use",
        "id": "c1",
        "name": "echo",
        "input": {"text": "a"},
    }


def test_consecutive_user_turns_merge() -> None:
    out = to_anthropic_messages(
        [Message("user", "task"), Message("user", "<summary>"), Message("assistant", "ok")]
    )
    assert [m["role"] for m in out] == ["user", "assistant"]
    assert len(out[0]["content"]) == 2


def test_empty_tool_result_placeholder() -> None:
    msgs = [
        Message("user", "go"),
        Message("assistant", "", tool_calls=(ToolCall("c1", "echo", {}),)),
        Message("tool", "", tool_call_id="c1"),
    ]
    assert to_anthropic_messages(msgs)[2]["content"][0]["content"] == "(no output)"  # type: ignore[index]


def test_tools_to_input_schema() -> None:
    spec = EchoTool().spec
    out = to_anthropic_tools([spec])
    assert out[0]["name"] == "echo" and out[0]["input_schema"] == spec.parameters
    empty = to_anthropic_tools([ToolSpec("n", "d", {})])
    assert empty[0]["input_schema"] == {"type": "object", "properties": {}}


# --- F2: history pairing check ----------------------------------------------------------


def test_tool_message_without_id_raises_bad_history() -> None:
    with pytest.raises(ProviderError) as info:
        to_anthropic_messages([Message("user", "x"), Message("tool", "secret-content")])
    assert info.value.code == "BAD_HISTORY"
    assert "secret-content" not in str(info.value) and "index 1" in str(info.value)


def test_orphan_tool_result_id_raises_before_any_request() -> None:
    calls: list[int] = []

    def handler(request: Any) -> Any:
        calls.append(1)
        return httpx2.Response(200, json=reply([text("x")]))

    bad = history()[:-1] + [Message("tool", "b", tool_call_id="WRONG")]
    with pytest.raises(ProviderError) as info:
        make(handler).complete(bad, [])
    assert info.value.code == "BAD_HISTORY" and calls == []
    assert "Why:" in str(info.value) and "Fix:" in str(info.value)


def test_unanswered_tool_use_raises_bad_history() -> None:
    with pytest.raises(ProviderError) as info:
        to_anthropic_messages(history()[:-1])  # c2 never answered
    assert info.value.code == "BAD_HISTORY"


# --- response translation ---------------------------------------------------------------


def convert(msg: Any) -> Any:
    return from_anthropic_message(msg, model="m", max_tokens=8192)


def test_end_turn_returns_text() -> None:
    out = convert(sdk_message([text("a"), text("b")]))
    assert (out.content, out.tool_calls) == ("ab", [])


def test_tool_use_returns_tool_calls() -> None:
    out = convert(sdk_message([tool_use()], "tool_use"))
    assert out.tool_calls == [ToolCall("toolu_1", "echo", {"text": "hi"})]


def test_max_tokens_is_not_silent() -> None:
    with pytest.raises(ProviderError) as info:
        convert(sdk_message([text("partial")], "max_tokens"))
    assert info.value.code == "MAX_TOKENS"
    assert "max_tokens=8192" in str(info.value) and "Fix:" in str(info.value)
    assert "partial" not in str(info.value)


def test_max_tokens_with_tool_use_still_raises() -> None:
    with pytest.raises(ProviderError) as info:
        convert(sdk_message([tool_use()], "max_tokens"))
    assert info.value.code == "MAX_TOKENS"


@pytest.mark.parametrize(
    ("stop", "code"),
    [
        ("refusal", "REFUSAL"),
        ("model_context_window_exceeded", "CONTEXT_WINDOW"),
        ("pause_turn", "PAUSED"),
        (None, "BAD_RESPONSE"),
    ],
)
def test_refusal_context_pause_unknown_raise(stop: str | None, code: str) -> None:
    with pytest.raises(ProviderError) as info:
        convert(sdk_message([text("x")], stop))
    assert info.value.code == code


def test_unknown_stop_reason_raises_via_wire() -> None:
    """The SDK parses an unlisted stop_reason as a plain str; it must fail closed."""
    with pytest.raises(ProviderError) as info:
        make(ok([text("x")], stop="brand_new_reason")).complete(USER_HI, [])
    assert info.value.code == "BAD_RESPONSE" and "brand_new_reason" in str(info.value)


def test_worst_case_bound_arithmetic() -> None:
    from master_finhub.runtime.anthropic_llm import worst_case_call_seconds

    assert worst_case_call_seconds() == 700.0 and worst_case_call_seconds(0) == 335.0


def test_refusal_omits_explanation() -> None:
    details = {"type": "refusal", "category": "cyber", "explanation": "SENTINEL_EXPL"}
    with pytest.raises(ProviderError) as info:
        convert(sdk_message([], "refusal", stop_details=details))
    assert "SENTINEL_EXPL" not in str(info.value) and "cyber" in str(info.value)


def test_empty_end_turn_is_error() -> None:
    with pytest.raises(ProviderError) as info:
        convert(sdk_message([]))
    assert info.value.code == "EMPTY_RESPONSE"


def test_unknown_block_type_raises_via_wire() -> None:
    """F5: unknown blocks parse as TextBlock objects; branch on .type from raw JSON."""
    handler = ok([text("a"), {"type": "mystery_block"}])
    with pytest.raises(ProviderError) as info:
        make(handler).complete(USER_HI, [])
    assert info.value.code == "BAD_RESPONSE" and "mystery_block" in str(info.value)


def test_thinking_block_raises() -> None:
    block = {"type": "thinking", "thinking": "hmm", "signature": "s"}
    with pytest.raises(ProviderError) as info:
        convert(sdk_message([block, text("a")]))
    assert "thinking" in str(info.value)


# --- construction -----------------------------------------------------------------------


def test_missing_key_fails_before_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    calls: list[int] = []

    def handler(request: Any) -> Any:
        calls.append(1)
        return httpx2.Response(200)

    with pytest.raises(ProviderError) as info:
        make(handler)
    assert info.value.code == "CONFIG" and "ANTHROPIC_API_KEY" in str(info.value)
    assert calls == []


def test_round_trip_via_mock_transport() -> None:
    sent: list[dict[str, Any]] = []
    replies = [reply([tool_use("toolu_9")], "tool_use"), reply([text("hi")])]

    def handler(request: Any) -> Any:
        sent.append(json.loads(request.content))
        return httpx2.Response(200, json=replies[len(sent) - 1])

    assert AgentLoop(make(handler), [EchoTool()]).run("echo hi") == "hi"
    second = sent[1]
    assert second["max_tokens"] == 8192 and second["model"] == "m" and "system" not in second
    assert second["messages"][-1]["content"][0]["tool_use_id"] == "toolu_9"
    assert sent[0]["tools"][0]["name"] == "echo"


def test_system_prompt_sent_when_set() -> None:
    sent: list[dict[str, Any]] = []

    def handler(request: Any) -> Any:
        sent.append(json.loads(request.content))
        return httpx2.Response(200, json=reply([text("x")]))

    make(handler, system="be brief").complete(USER_HI, [])
    assert sent[0]["system"] == "be brief"


# --- F1: retry / timeout / cost ceiling --------------------------------------------------


def test_timeout_values_reach_the_wire() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: Any) -> Any:
        seen.append(dict(request.extensions["timeout"]))
        return httpx2.Response(200, json=reply([text("x")]))

    make(handler).complete(USER_HI, [])
    assert seen[0]["read"] == READ_TIMEOUT_S and seen[0]["connect"] == CONNECT_TIMEOUT_S
    assert READ_TIMEOUT_S < 600  # strictly tighter than the SDK default


def test_default_max_retries_reach_the_client_and_call_count() -> None:
    calls: list[int] = []

    def handler(request: Any) -> Any:
        calls.append(1)
        return httpx2.Response(500, json={})

    llm = make(handler)
    assert llm._client.max_retries == anthropic_llm.DEFAULT_MAX_RETRIES == 1
    with pytest.raises(ProviderError):
        llm.complete(USER_HI, [])
    assert len(calls) == 2  # one try plus one retry


def test_max_retries_zero_means_single_attempt() -> None:
    calls: list[int] = []

    def handler(request: Any) -> Any:
        calls.append(1)
        return httpx2.Response(500, json={})

    with pytest.raises(ProviderError):
        make(handler, max_retries=0).complete(USER_HI, [])
    assert len(calls) == 1


def test_max_retries_above_ceiling_rejected() -> None:
    with pytest.raises(ProviderError) as info:
        make(ok(), max_retries=anthropic_llm.MAX_RETRIES_CEILING + 1)
    assert info.value.code == "CONFIG"


def test_max_tokens_above_hard_ceiling_rejected() -> None:
    with pytest.raises(ProviderError) as info:
        make(ok(), max_tokens=21_334)
    assert info.value.code == "CONFIG"


@pytest.mark.parametrize(
    "headers",
    [
        {"retry-after": "86400"},
        {"retry-after-ms": "86400000"},
        {"retry-after": "Wed, 21 Oct 2099 07:28:00 GMT"},
    ],
)
def test_server_requested_wait_is_capped(
    headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    seq = [
        httpx2.Response(429, json={}, headers=headers),
        httpx2.Response(200, json=reply([text("x")])),
    ]
    out = make(lambda request: seq.pop(0)).complete(USER_HI, [])
    assert out.content == "x"
    assert len(sleeps) == 1 and 0 <= sleeps[0] <= RETRY_AFTER_CAP_S


def test_cost_ceiling_documented_in_module_docstring() -> None:
    doc = anthropic_llm.__doc__ or ""
    assert "max_steps x max_tokens" in doc and "worst-case" in doc.lower()


# --- F2: each SDK class gets its own three-part message ----------------------------------

ERR_BODY = {"type": "error", "error": {"type": "invalid_request_error", "message": "x"}}


@pytest.mark.parametrize(
    ("code_http", "code", "fix_has", "fix_lacks"),
    [
        (400, "INVALID_REQUEST", "invalid_request_error", "model id"),
        (401, "AUTH", "ANTHROPIC_API_KEY", "model id"),
        (403, "AUTH", "access", "model id"),
        (404, "MODEL_NOT_FOUND", "tier_models", "invalid_request_error"),
        (409, "CONFLICT", "rerun", "model id"),
        (413, "REQUEST_TOO_LARGE", "context", "model id"),
        (422, "INVALID_REQUEST", "rejected", "model id"),
        (429, "RATE_LIMIT", "wait", "model id"),
        (500, "SERVER", "later", "model id"),
        (529, "SERVER", "later", "model id"),
        (418, "API_ERROR", "request id", "model id"),
    ],
)
def test_status_errors_map_to_own_messages(
    code_http: int, code: str, fix_has: str, fix_lacks: str
) -> None:
    with pytest.raises(ProviderError) as info:
        make(status(code_http, ERR_BODY, **{"request-id": "req_123"}), max_retries=0).complete(
            USER_HI, []
        )
    exc = info.value
    fix = str(exc).split("Fix:")[1]
    assert exc.code == code and fix_has.lower() in fix.lower() and fix_lacks not in fix
    assert str(exc).count("\n") == 2 and str(code_http) in str(exc)


def test_connection_error_honest() -> None:
    def handler(request: Any) -> Any:
        raise httpx2.ConnectError("boom")

    with pytest.raises(ProviderError) as info:
        make(handler, max_retries=0).complete(USER_HI, [])
    assert info.value.code == "CONNECTION"
    assert "nothing was sent" not in str(info.value)
    assert "may or may not" in str(info.value)


def test_timeout_maps_to_timeout() -> None:
    def handler(request: Any) -> Any:
        raise httpx2.ReadTimeout("slow")

    with pytest.raises(ProviderError) as info:
        make(handler, max_retries=0).complete(USER_HI, [])
    assert info.value.code == "TIMEOUT"


# --- F3: leaks via exception chaining ----------------------------------------------------


def _chain(exc: BaseException) -> list[BaseException]:
    seen: list[BaseException] = []
    todo: list[BaseException | None] = [exc]
    while todo:
        cur = todo.pop()
        if cur is None or any(cur is s for s in seen):
            continue
        seen.append(cur)
        todo += [cur.__cause__, cur.__context__]
    return seen


def test_api_key_and_prompt_never_in_error_or_chain() -> None:
    body = {"error": {"type": "authentication_error", "message": f"{DUMMY_KEY} {PROMPT_SENTINEL}"}}

    def handler(request: Any) -> Any:
        assert DUMMY_KEY in request.headers["x-api-key"]  # the key really is on the request
        return httpx2.Response(401, json=body)

    with pytest.raises(ProviderError) as info:
        make(handler, max_retries=0).complete([Message("user", PROMPT_SENTINEL)], [])
    exc = info.value
    assert exc.__cause__ is None and exc.__context__ is None
    for link in _chain(exc):
        blob = str(link) + repr(link) + repr(link.args)
        assert DUMMY_KEY not in blob and PROMPT_SENTINEL not in blob
    rendered = "".join(traceback.format_exception(exc))
    assert DUMMY_KEY not in rendered and PROMPT_SENTINEL not in rendered


def test_connection_failure_chain_is_clean() -> None:
    def handler(request: Any) -> Any:
        raise httpx2.ConnectError(f"{PROMPT_SENTINEL} {DUMMY_KEY}")

    with pytest.raises(ProviderError) as info:
        make(handler, max_retries=0).complete([Message("user", PROMPT_SENTINEL)], [])
    assert info.value.__context__ is None and info.value.__cause__ is None
    assert len(_chain(info.value)) == 1


# --- logging ----------------------------------------------------------------------------


def test_no_prompt_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    make(ok()).complete([Message("user", PROMPT_SENTINEL)], [])
    assert PROMPT_SENTINEL not in caplog.text


def test_every_sdk_logger_tree_is_quiet_after_construction(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    import httpcore2  # noqa: F401

    make(ok())
    for name in list(logging.root.manager.loggerDict):
        if name.split(".")[0] in LOGGER_NAMES:
            assert not logging.getLogger(name).isEnabledFor(logging.DEBUG), name
    for name in LOGGER_NAMES:
        assert not logging.getLogger(name).isEnabledFor(logging.INFO), name


def test_clamp_honours_deliberate_anthropic_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_LOG", "info")
    logging.getLogger("httpcore2").setLevel(logging.INFO)
    make(ok())
    assert logging.getLogger("httpcore2").level == logging.INFO


def test_logger_clamp_covers_every_logger_root_the_http_stack_uses() -> None:
    """Find logger roots from installed source, not memory (judge F4)."""
    site_dirs = [Path(p) for p in site.getsitepackages()]
    found: set[str] = set()
    # anyio is deliberately not scanned: its only logger is the async TLS stream, which the
    # sync client never uses.
    for pkg in ("anthropic", "httpx2", "httpcore2", "h11", "sniffio", "jiter"):
        for base in site_dirs:
            for path in (base / pkg).rglob("*.py") if (base / pkg).is_dir() else []:
                src = path.read_text(encoding="utf-8", errors="ignore")
                for lit in re.findall(r'getLogger\(\s*"([\w.]+)"', src):
                    found.add(lit.split(".")[0])
                if "getLogger(__name__)" in src:
                    found.add(pkg)
    assert found, "no logger usages found - scan is broken"
    assert found <= set(LOGGER_NAMES), found - set(LOGGER_NAMES)


# --- SDK stays the single retry owner ----------------------------------------------------


def test_sdk_retry_is_only_retry() -> None:
    calls: list[int] = []

    def handler(request: Any) -> Any:
        calls.append(1)
        if len(calls) == 1:
            return httpx2.Response(429, json={})
        return httpx2.Response(200, json=reply([text("x")]))

    assert make(handler, max_retries=1).complete(USER_HI, []).content == "x"
    assert len(calls) == 2
