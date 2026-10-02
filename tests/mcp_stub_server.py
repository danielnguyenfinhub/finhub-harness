"""Stub stdio MCP server for tests (stdlib only, newline-delimited JSON-RPC, synthetic data).

Modes (argv[1:]): normal (no flag), --paged, --die-on-call, --never-answer, --version <v>,
--huge-line, --endless-pages, --ask-client <n>, --ignore-eof [--ignore-term].
--ignore-eof keeps the process alive after stdin EOF; --ignore-term also ignores SIGTERM (kill-only).
Every message received is appended as one JSON line to the file named by MCP_STUB_LOG.
"""

import json
import os
import signal
import sys
import time
from typing import Any

ARGS = sys.argv[1:]
LOG = os.environ.get("MCP_STUB_LOG")
SECRET = os.environ.get("MCP_STUB_SECRET", "")
TOOLS = [
    {"name": "echo", "description": "echo text", "inputSchema": {"type": "object"}},
    {"name": "fail", "description": "always fails", "inputSchema": {"type": "object"}},
]


def send(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def reply(req_id: Any, result: dict[str, Any]) -> None:
    send({"jsonrpc": "2.0", "id": req_id, "result": result})


def text(value: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": value}], "isError": is_error}


def arg_after(flag: str, default: str) -> str:
    return ARGS[ARGS.index(flag) + 1] if flag in ARGS else default


def handle_list(req_id: Any, params: dict[str, Any]) -> None:
    if "--huge-line" in ARGS:
        sys.stdout.write("x" * 5_000_000)  # no newline: the client must refuse to buffer it
        sys.stdout.flush()
        time.sleep(30)
    elif "--endless-pages" in ARGS:
        reply(req_id, {"tools": TOOLS[:1], "nextCursor": "again"})
    elif "--paged" in ARGS:
        if params.get("cursor") == "p2":
            reply(req_id, {"tools": TOOLS[1:]})
        else:
            reply(req_id, {"tools": TOOLS[:1], "nextCursor": "p2"})
    else:
        reply(req_id, {"tools": TOOLS})


def handle_call(req_id: Any, params: dict[str, Any]) -> None:
    if "--die-on-call" in ARGS:
        os._exit(3)
    if "--never-answer" in ARGS:
        return
    if "--ask-client" in ARGS:
        for i in range(int(arg_after("--ask-client", "1"))):
            send({"jsonrpc": "2.0", "id": f"s{i}", "method": "sampling/createMessage"})
    if params.get("name") == "fail":
        reply(req_id, text(f"boom {SECRET}", True))
    else:
        reply(req_id, text(str(params.get("arguments", {}).get("text", ""))))


def main() -> None:
    if "--ignore-term" in ARGS:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    for line in sys.stdin:
        msg = json.loads(line)
        if LOG:
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(msg) + "\n")
        method, req_id, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if method == "initialize":
            reply(
                req_id,
                {
                    "protocolVersion": arg_after("--version", "2025-06-18"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "stub", "version": "0", "envKeys": sorted(os.environ)},
                },
            )
        elif method == "tools/list":
            handle_list(req_id, params)
        elif method == "tools/call":
            handle_call(req_id, params)
    if "--ignore-eof" in ARGS:
        while True:
            time.sleep(1)


if __name__ == "__main__":
    main()
