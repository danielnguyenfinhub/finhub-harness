"""Command line entry point: ``python -m master_finhub.cli "echo hi"``."""

from __future__ import annotations

import argparse
import sys

from master_finhub.runtime.anthropic_llm import ProviderError
from master_finhub.runtime.context import ContextManager
from master_finhub.runtime.fake_llm import ECHO_PREFIX, ScriptedLLM
from master_finhub.runtime.loop import LLM, AgentLoop, AgentLoopError
from master_finhub.runtime.router import Router, RouterConfigError
from master_finhub.tools.builtins.echo import EchoTool
from master_finhub.tools.safety import guard_tool_call


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="master-finhub", description="Run the agent loop.")
    parser.add_argument("prompt", help=f"Prompt. No real LLM yet: use '{ECHO_PREFIX}<text>'.")
    parser.add_argument(
        "--profile",
        default=None,
        help="Model profile (judge, miner, ...). Omit to use the scripted echo LLM.",
    )
    args = parser.parse_args(argv)
    if args.profile is not None:
        try:
            llm: LLM = Router().build_llm(args.profile)
        except RouterConfigError as exc:
            print(exc, file=sys.stderr)
            return 2
        except ProviderError as exc:
            print(f"Model call failed: {exc}", file=sys.stderr)
            return 1
        return _run(llm, args.prompt)
    if not args.prompt.startswith(ECHO_PREFIX):
        print(
            f"Only prompts starting '{ECHO_PREFIX}' work until a real LLM is wired.",
            file=sys.stderr,
        )
        return 2
    return _run(ScriptedLLM(), args.prompt)


def _run(llm: LLM, prompt: str) -> int:
    try:
        loop = AgentLoop(llm, [EchoTool()], context=ContextManager(), guard=guard_tool_call)
        print(loop.run(prompt))
    except AgentLoopError as exc:
        print(f"Agent failed: {exc}", file=sys.stderr)
        return 1
    except ProviderError as exc:
        print(f"Model call failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
