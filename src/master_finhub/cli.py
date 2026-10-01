"""Command line entry point: ``python -m master_finhub.cli "echo hi"``."""

from __future__ import annotations

import argparse
import sys

from master_finhub.runtime.fake_llm import ECHO_PREFIX, ScriptedLLM
from master_finhub.runtime.loop import AgentLoop, AgentLoopError
from master_finhub.tools.builtins.echo import EchoTool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="master-finhub", description="Run the agent loop.")
    parser.add_argument("prompt", help=f"Prompt. No real LLM yet: use '{ECHO_PREFIX}<text>'.")
    args = parser.parse_args(argv)
    if not args.prompt.startswith(ECHO_PREFIX):
        print(
            f"Only prompts starting '{ECHO_PREFIX}' work until a real LLM is wired.",
            file=sys.stderr,
        )
        return 2
    try:
        print(AgentLoop(ScriptedLLM(), [EchoTool()]).run(args.prompt))
    except AgentLoopError as exc:
        print(f"Agent failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
