"""Thin, non-streaming Anthropic Messages adapter implementing ``runtime.loop.LLM`` (slice 4).

Message translation adapted (idea, not code) from MIT-licensed crewAI
``references/crewai/lib/crewai/src/crewai/llms/providers/anthropic/completion.py``
(``_format_messages``, ~lines 845-937: tool results buffered into one user turn, ``tool_use``
blocks, ``system`` only when non-empty) and from MIT deepseek-harness
``references/deepseek_harness/packages/llm/llm-pi-ai/src/{context,stream}.ts`` (empty tool-result
placeholder ``context.ts:163``, empty completion is an error ``stream.ts:95``, truncation is its
own outcome ``stream.ts:105``). Everything else is written against the installed SDK source.

The ``anthropic`` SDK is imported lazily inside ``AnthropicLLM.__init__`` so the core loop, router
and CLI import (and the CLI echo path runs) with no SDK installed and no API key.

Cost and time ceilings (per run, all values are named constants / constructor parameters)
-----------------------------------------------------------------------------------------
* Output tokens per call are hard-capped at ``router.MAX_NONSTREAMING_TOKENS`` (21,333); the
  default is ``router.DEFAULT_MAX_TOKENS`` (8,192).
* Output-token ceiling per run = max_steps x max_tokens = 20 x 8,192 = 163,840 tokens at the
  defaults (20 = ``loop.DEFAULT_MAX_STEPS``). Failed retried attempts may be billed too, so the
  absolute ceiling is that figure x (max_retries + 1) = 327,680 at the default ``max_retries=1``.
  Input tokens per step are bounded by the context window (slice 2). There is no dollar budget.
* Worst-case wall-clock per ``complete()`` call, see ``worst_case_call_seconds``:
  (max_retries + 1) x (connect 5 s + write 30 s + read 300 s) + max_retries x 30 s retry wait
  = 2 x 335 + 30 = 700 s at the defaults. Caveats: the read timeout is per socket read, not a
  total deadline, so a server that trickles bytes can exceed it; there is no overall deadline.
* The SDK retries 408/409/429/>=500 and connection/timeout errors (status rules at
  _base_client.py:875-880, ``retry-after`` parsing at :804, exception retries in the request
  loop at :1174-1183 via ``_should_retry_exception``).
* The SDK itself obeys a server ``retry-after`` with no cap (anthropic/_base_client.py:~836:
  ``min(retry_after, 4_294_967.0)``) and defaults to a 600 s read timeout (_constants.py:10). The
  SDK offers no option to cap it, so a response hook clamps ``retry-after`` / ``retry-after-ms``
  to ``RETRY_AFTER_CAP_S`` before the SDK reads them, and ``max_retries`` is kept low (default 1,
  ceiling 2) with an explicit ``timeout``.

Logging side effect: building the provider raises the level of the ``anthropic``, ``httpx2`` and
``httpcore2`` logger trees to at least WARNING (never lowers a level, never touches the root
logger or handlers), because at DEBUG they log request bodies (the prompt) and response headers.
It is skipped when ``ANTHROPIC_LOG`` is set, so a deliberate debug session is honoured.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Final, Literal, cast

from master_finhub.runtime.loop import AssistantMessage, Message, ToolCall, ToolSpec
from master_finhub.runtime.router import DEFAULT_MAX_TOKENS, MAX_NONSTREAMING_TOKENS

if TYPE_CHECKING:
    import httpx2
    from anthropic import Anthropic
    from anthropic.types import (
        Message as SdkMessage,
    )
    from anthropic.types import (
        MessageParam,
        TextBlockParam,
        ToolParam,
        ToolResultBlockParam,
        ToolUseBlockParam,
    )

API_KEY_ENV: Final = "ANTHROPIC_API_KEY"
EMPTY_TOOL_RESULT: Final = "(no output)"
EMPTY_TEXT: Final = "(empty)"

# --- explicit client options (F1). Verified names/types in anthropic/_client.py:166-167. ---
DEFAULT_MAX_RETRIES: Final = 1
MAX_RETRIES_CEILING: Final = 2  # == anthropic DEFAULT_MAX_RETRIES (_constants.py:10)
CONNECT_TIMEOUT_S: Final = 5.0
WRITE_TIMEOUT_S: Final = 30.0
READ_TIMEOUT_S: Final = 300.0
POOL_TIMEOUT_S: Final = 5.0
RETRY_AFTER_CAP_S: Final = 30.0

# Every logger tree the SDK's HTTP stack uses (found from installed source, see test).
LOGGER_NAMES: Final = ("anthropic", "httpx2", "httpcore2")

ErrorCode = Literal[
    "CONFIG",
    "AUTH",
    "RATE_LIMIT",
    "SERVER",
    "TIMEOUT",
    "CONNECTION",
    "INVALID_REQUEST",
    "MODEL_NOT_FOUND",
    "REQUEST_TOO_LARGE",
    "CONFLICT",
    "API_ERROR",
    "MAX_TOKENS",
    "CONTEXT_WINDOW",
    "REFUSAL",
    "PAUSED",
    "EMPTY_RESPONSE",
    "BAD_RESPONSE",
    "BAD_HISTORY",
]

# Closed enum of API error types (anthropic/types/shared/error_type.py): safe to show.
_ERROR_TYPES: Final = frozenset(
    {
        "invalid_request_error",
        "authentication_error",
        "permission_error",
        "not_found_error",
        "rate_limit_error",
        "timeout_error",
        "overloaded_error",
        "api_error",
        "billing_error",
    }
)
_OPAQUE_ID: Final = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class ProviderError(RuntimeError):
    """Three-part provider failure. ``str(exc)`` is built only from safe fields."""

    def __init__(self, code: ErrorCode, what: str, why: str, fix: str) -> None:
        super().__init__(f"{what}\nWhy: {why}\nFix: {fix}")
        self.code: ErrorCode = code


def worst_case_call_seconds(max_retries: int = DEFAULT_MAX_RETRIES) -> float:
    """Documented upper bound for one ``complete()`` call (see module docstring caveats)."""
    attempt = CONNECT_TIMEOUT_S + WRITE_TIMEOUT_S + READ_TIMEOUT_S
    return (max_retries + 1) * attempt + max_retries * RETRY_AFTER_CAP_S


# --- pure translation --------------------------------------------------------------------


def _bad_history(
    why: str, fix: str = "this is a harness bug: report it with the step count."
) -> Any:
    return ProviderError("BAD_HISTORY", "The conversation history is not valid to send.", why, fix)


def to_anthropic_messages(messages: Sequence[Message]) -> list[MessageParam]:
    """Translate the loop history; verifies tool_use / tool_result ids pair up (F2)."""
    out: list[MessageParam] = []
    buffer: list[TextBlockParam | ToolResultBlockParam] = []
    open_ids: list[str] = []

    def flush() -> None:
        if buffer:
            out.append({"role": "user", "content": list(buffer)})
            buffer.clear()

    for index, msg in enumerate(messages):
        if msg.role == "user":
            buffer.append({"type": "text", "text": msg.content or EMPTY_TEXT})
        elif msg.role == "tool":
            if msg.tool_call_id is None:
                raise _bad_history(f"the tool message at index {index} has no tool_call_id.")
            if msg.tool_call_id not in open_ids:
                raise _bad_history(
                    f"the tool result at index {index} does not answer a tool call made by "
                    "the assistant turn just before it."
                )
            open_ids.remove(msg.tool_call_id)
            buffer.append(
                {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content or EMPTY_TOOL_RESULT,
                }
            )
        else:
            if open_ids:
                raise _bad_history(
                    f"{len(open_ids)} tool call(s) before index {index} never got a result."
                )
            flush()
            blocks: list[TextBlockParam | ToolUseBlockParam] = []
            if msg.content:
                blocks.append({"type": "text", "text": msg.content})
            for call in msg.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": dict(call.arguments),
                    }
                )
            open_ids = [c.id for c in msg.tool_calls]
            out.append(
                {"role": "assistant", "content": blocks or [{"type": "text", "text": EMPTY_TEXT}]}
            )
    if open_ids:
        raise _bad_history(
            f"{len(open_ids)} tool call(s) at the end of the history have no result."
        )
    flush()
    return out


def to_anthropic_tools(tools: Sequence[ToolSpec]) -> list[ToolParam]:
    empty: dict[str, Any] = {"type": "object", "properties": {}}
    return [
        cast(
            "ToolParam",
            {"name": t.name, "description": t.description, "input_schema": t.parameters or empty},
        )
        for t in tools
    ]


def from_anthropic_message(reply: SdkMessage, *, model: str, max_tokens: int) -> AssistantMessage:
    """Gate on ``stop_reason``; never return a partial or unknown-shaped reply as complete."""
    stop = reply.stop_reason
    if stop == "max_tokens":
        raise ProviderError(
            "MAX_TOKENS",
            f"The reply from {model} was cut off at max_tokens={max_tokens}.",
            "a truncated answer or tool call must never be used as if it were complete.",
            f"rerun with a larger max_tokens (up to {MAX_NONSTREAMING_TOKENS}) or a shorter task.",
        )
    if stop == "model_context_window_exceeded":
        raise ProviderError(
            "CONTEXT_WINDOW",
            f"The conversation no longer fits {model}'s context window.",
            "the model stopped because the context is full.",
            "lower ContextManager(context_window_tokens=...) so older turns are compacted.",
        )
    if stop == "refusal":
        category = reply.stop_details.category if reply.stop_details else None
        extra = f" (category: {category})" if category else ""
        raise ProviderError(
            "REFUSAL",
            f"{model} declined to answer{extra}.",
            "the model's safety policy refused this request.",
            "reword or narrow the task; no answer was produced.",
        )
    if stop == "pause_turn":
        raise ProviderError(
            "PAUSED",
            f"{model} paused the turn.",
            "only server-side tools pause turns and this harness sends none.",
            "report this: an unexpected stop_reason was returned.",
        )
    if stop not in ("end_turn", "stop_sequence", "tool_use"):
        raise ProviderError(
            "BAD_RESPONSE",
            f"{model} returned an unrecognised stop_reason: {stop!r}.",
            "this harness only understands end_turn, stop_sequence, tool_use and the error stops.",
            "upgrade master-finhub and the anthropic SDK; report the value if it persists.",
        )
    text_parts: list[str] = []
    calls: list[ToolCall] = []
    for block in reply.content:
        btype = str(block.type)  # F5: branch on .type, never isinstance(TextBlock)
        if btype == "text":
            text_parts.append(cast("str", getattr(block, "text", "")))
        elif btype == "tool_use":
            calls.append(
                ToolCall(
                    cast("str", getattr(block, "id", "")),
                    cast("str", getattr(block, "name", "")),
                    dict(cast("dict[str, Any]", getattr(block, "input", {}))),
                )
            )
        else:
            raise ProviderError(
                "BAD_RESPONSE",
                f"{model} returned a content block of unsupported type '{btype}'.",
                "this harness handles only text and tool_use blocks and will not drop others.",
                "run without extended thinking or server tools, or upgrade master-finhub.",
            )
    text = "".join(text_parts)
    if stop == "tool_use" and not calls:
        raise ProviderError(
            "BAD_RESPONSE",
            f"{model} said it used a tool but sent no tool call.",
            "stop_reason was tool_use with no tool_use block.",
            "rerun; report it if it repeats.",
        )
    if not text and not calls:
        raise ProviderError(
            "EMPTY_RESPONSE",
            f"{model} returned an empty reply.",
            "the model stopped cleanly but produced no text and no tool call.",
            "rerun; rephrase the task if it repeats.",
        )
    return AssistantMessage(text, calls)


# --- error mapping (F2) ------------------------------------------------------------------


def _error_type(body: object) -> str:
    err = body.get("error", body) if isinstance(body, dict) else None
    value = err.get("type") if isinstance(err, dict) else None
    return value if isinstance(value, str) and value in _ERROR_TYPES else "unspecified"


def _request_id(exc: Any) -> str:
    rid = getattr(exc, "request_id", None)
    return rid if isinstance(rid, str) and _OPAQUE_ID.match(rid) else "not provided"


def map_sdk_error(exc: BaseException, *, model: str, max_tokens: int, sdk: Any) -> ProviderError:
    """Rebuild an SDK exception as a ProviderError from safe fields only (A127).

    Status -> class mapping verified at anthropic/_client.py:555-584 (400/401/403/404/409/413/
    422/429/529/>=500; 409 -> ConflictError at :567). APITimeoutError subclasses
    APIConnectionError (_exceptions.py:100), so it is checked first.

    Uses only: exception class, int status, closed-enum API error type, a validated opaque
    request id, model id and max_tokens. Never ``str(exc)``, ``exc.message``, ``exc.body``,
    headers or request content.
    """
    if isinstance(exc, sdk.APITimeoutError):
        return ProviderError(
            "TIMEOUT",
            f"The call to {model} timed out.",
            f"no reply arrived within {READ_TIMEOUT_S:.0f}s.",
            "rerun; shorten the task or lower max_tokens if it repeats.",
        )
    if isinstance(exc, sdk.APIConnectionError):
        return ProviderError(
            "CONNECTION",
            "Could not reach the Anthropic API.",
            "no reply was received (network, DNS, proxy or TLS failure).",
            "check the internet connection and proxy, then rerun. The request may or may not "
            "have been processed, so check usage before retrying if cost matters.",
        )
    if isinstance(exc, sdk.APIStatusError):
        status = int(exc.status_code)
        rid = _request_id(exc)
        etype = _error_type(getattr(exc, "body", None))
        what = f"The Anthropic API returned HTTP {status} for {model} (request id {rid})."
        if status == 401:
            return ProviderError(
                "AUTH",
                what,
                "the API key was not accepted.",
                f"check {API_KEY_ENV} is a valid, active key; never paste it into chat or code.",
            )
        if status == 403:
            return ProviderError(
                "AUTH",
                what,
                "the API key is not allowed to use this model or workspace.",
                f"check the key has access to model {model} in the Anthropic console.",
            )
        if status == 404:
            return ProviderError(
                "MODEL_NOT_FOUND",
                what,
                f"model {model} does not exist for this account.",
                "set a valid id in Router(tier_models={...}) and rerun.",
            )
        if status == 413:
            return ProviderError(
                "REQUEST_TOO_LARGE",
                what,
                "the request body is over the API size limit.",
                "lower ContextManager(context_window_tokens=...) or shorten the task.",
            )
        if status in (400, 422):
            return ProviderError(
                "INVALID_REQUEST",
                what,
                "the API could not accept the request as sent.",
                f"the request was rejected (API error type: {etype}); check tool definitions "
                "and history, rerun, and quote the request id if it repeats.",
            )
        if status == 409:
            return ProviderError(
                "CONFLICT", what, "the API reported a transient conflict.", "rerun the task."
            )
        if status == 429:
            return ProviderError(
                "RATE_LIMIT",
                what,
                "the account is rate limited (the SDK already retried).",
                "wait a minute and rerun, or use a lower-tier profile.",
            )
        if status >= 500:
            return ProviderError(
                "SERVER",
                what,
                "Anthropic is degraded or overloaded; no reply was returned.",
                "rerun later.",
            )
        return ProviderError(
            "API_ERROR",
            what,
            "an unexpected status was returned.",
            "report the status and request id.",
        )
    return ProviderError(
        "API_ERROR",
        f"The Anthropic SDK failed ({type(exc).__name__}).",
        "an SDK-level error occurred before a usable reply was received.",
        f"rerun; check max_tokens={max_tokens} and the installed anthropic version.",
    )


# --- client plumbing ---------------------------------------------------------------------


def _clamp_retry_after(response: httpx2.Response) -> None:
    """Response hook: no server header may make the SDK sleep longer than the cap.

    Unparseable values (e.g. an HTTP-date) are dropped so the SDK falls back to its own
    <= 8 s backoff (_constants.py:14).
    """
    for name, scale in (("retry-after-ms", 1000.0), ("retry-after", 1.0)):
        raw = response.headers.get(name)
        if raw is None:
            continue
        try:
            value = float(raw)
        except ValueError:
            del response.headers[name]
            continue
        if value > RETRY_AFTER_CAP_S * scale:
            response.headers[name] = repr(RETRY_AFTER_CAP_S * scale)


def _quiet_sdk_loggers() -> None:
    if os.environ.get("ANTHROPIC_LOG") is not None:
        return
    for name in LOGGER_NAMES:
        logger = logging.getLogger(name)
        logger.setLevel(max(logger.level, logging.WARNING))


def _config_error(what: str, why: str, fix: str) -> ProviderError:
    return ProviderError("CONFIG", what, why, fix)


class AnthropicLLM:
    """Satisfies ``runtime.loop.LLM`` structurally. One non-streaming Messages call per step."""

    def __init__(
        self,
        model: str,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        system: str = "",
        max_retries: int = DEFAULT_MAX_RETRIES,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        if not 1 <= max_tokens <= MAX_NONSTREAMING_TOKENS:
            raise _config_error(
                f"max_tokens={max_tokens} is outside the allowed range.",
                f"one reply may use 1 to {MAX_NONSTREAMING_TOKENS} output tokens.",
                f"use a value between 1 and {MAX_NONSTREAMING_TOKENS}.",
            )
        if not 0 <= max_retries <= MAX_RETRIES_CEILING:
            raise _config_error(
                f"max_retries={max_retries} is outside the allowed range.",
                "the SDK honours server wait requests, so retries are kept low on purpose.",
                f"use 0 to {MAX_RETRIES_CEILING}.",
            )
        try:
            import anthropic
            import httpx2
        except ImportError:
            raise _config_error(
                "The Anthropic provider is not installed.",
                "the optional 'anthropic' extra is missing from this environment.",
                'run: pip install -e ".[anthropic]"',
            ) from None
        if not os.environ.get(API_KEY_ENV):
            raise _config_error(
                "No Anthropic API key is configured.",
                f"{API_KEY_ENV} is not set in the environment.",
                f"set {API_KEY_ENV} in your shell or .env (never in code), "
                "or run without --profile to use the scripted LLM.",
            )
        _quiet_sdk_loggers()
        timeout = httpx2.Timeout(
            connect=CONNECT_TIMEOUT_S,
            read=READ_TIMEOUT_S,
            write=WRITE_TIMEOUT_S,
            pool=POOL_TIMEOUT_S,
        )
        http_kwargs: dict[str, Any] = {
            "timeout": timeout,
            "event_hooks": {"response": [_clamp_retry_after]},
        }
        if transport is not None:
            http_kwargs["transport"] = transport
        self._client: Anthropic = anthropic.Anthropic(
            max_retries=max_retries,
            timeout=timeout,
            http_client=anthropic.DefaultHttpxClient(**http_kwargs),
        )
        self._omit: Any = anthropic.omit
        self._sdk: Any = anthropic
        self._model = model
        self._max_tokens = max_tokens
        self._system = system

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        sdk = self._sdk
        params = to_anthropic_messages(messages)
        tool_params = to_anthropic_tools(tools)
        error: ProviderError | None = None
        reply: SdkMessage | None = None
        try:
            reply = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=params,
                system=self._system or self._omit,
                tools=tool_params or self._omit,
            )
        except sdk.AnthropicError as exc:
            error = map_sdk_error(exc, model=self._model, max_tokens=self._max_tokens, sdk=sdk)
        # F3: raise OUTSIDE the except block so the SDK exception (request headers with the key,
        # request body with the prompt) is never attached as __context__/__cause__.
        if error is not None:
            raise error
        assert reply is not None
        return from_anthropic_message(reply, model=self._model, max_tokens=self._max_tokens)
