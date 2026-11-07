"""Command line entry point: ``python -m master_finhub.cli "echo hi"``."""

from __future__ import annotations

import argparse
import sys

from master_finhub.orchestration.dag_engine import (
    CheckpointError,
    CheckpointStore,
    RunWriter,
    validate_run_id,
)
from master_finhub.runtime.anthropic_llm import ProviderError
from master_finhub.runtime.context import ContextManager
from master_finhub.runtime.fake_llm import ECHO_PREFIX, ScriptedLLM
from master_finhub.runtime.loop import (
    LLM,
    AgentLoop,
    AgentLoopError,
    LoopSnapshot,
    ResumeBlocked,
    ToolGuard,
)
from master_finhub.runtime.router import Router, RouterConfigError
from master_finhub.sandbox.workspace import WORKSPACE_ENV_VAR, Workspace
from master_finhub.tools import guard_factory
from master_finhub.tools.builtins.echo import EchoTool
from master_finhub.tools.guard_factory import DEFAULT_TOOL_CLASSES, MODES
from master_finhub.tools.permissions import DEFAULT_MODE, Mode, ToolClass

SCRIPTED_PROFILE = "scripted"
TOOL_CLASSES: dict[str, ToolClass] = DEFAULT_TOOL_CLASSES  # one entry per tool the CLI registers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="master-finhub", description="Run the agent loop.")
    parser.add_argument(
        "prompt", nargs="?", help=f"Prompt. No real LLM yet: use '{ECHO_PREFIX}<text>'."
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Model profile (judge, miner, ...). Omit to use the scripted echo LLM.",
    )
    parser.add_argument(
        "--mode",
        choices=MODES,
        default=None,
        help=(
            f"Permission mode for tool calls (default {DEFAULT_MODE}). "
            "A resumed run keeps its saved mode and cannot be widened."
        ),
    )
    saving = parser.add_mutually_exclusive_group()
    saving.add_argument("--run-id", metavar="NAME", help="Save every step of this run under NAME.")
    saving.add_argument(
        "--resume", metavar="NAME", help="Continue the saved run NAME from its last step."
    )
    args = parser.parse_args(argv)
    if args.resume is not None:
        if args.prompt is not None:
            print("--resume takes no prompt: the saved run already has one.", file=sys.stderr)
            return 2
    elif args.prompt is None:
        parser.error("a prompt is required (or use --resume NAME)")
    store: CheckpointStore | None = None
    if args.run_id is not None or args.resume is not None:
        try:
            store = CheckpointStore(Workspace())
        except (FileNotFoundError, NotADirectoryError):
            print(
                "Checkpointing needs a workspace folder. "
                f"Set {WORKSPACE_ENV_VAR} to an existing folder.",
                file=sys.stderr,
            )
            return 2
    try:
        if args.resume is not None:
            assert store is not None
            return _resume(store, args.resume, args.profile, args.mode)
        return _start(str(args.prompt), args.profile, store, args.run_id, args.mode or DEFAULT_MODE)
    except CheckpointError as exc:
        print(exc, file=sys.stderr)
        return 1


def build_guard(mode: Mode) -> ToolGuard:
    """The base command guard first, then the mode guard; both judge every tool call."""
    return guard_factory.build_guard(mode, TOOL_CLASSES)


def _build_llm(profile: str | None) -> LLM:
    return ScriptedLLM() if profile in (None, SCRIPTED_PROFILE) else Router().build_llm(profile)


def _start(
    prompt: str,
    profile: str | None,
    store: CheckpointStore | None,
    run_id: str | None,
    mode: Mode,
) -> int:
    if profile is not None:
        try:
            llm = _build_llm(profile)
        except RouterConfigError as exc:
            print(exc, file=sys.stderr)
            return 2
        except ProviderError as exc:
            print(f"Model call failed: {exc}", file=sys.stderr)
            return 1
    elif not prompt.startswith(ECHO_PREFIX):
        print(
            f"Only prompts starting '{ECHO_PREFIX}' work until a real LLM is wired.",
            file=sys.stderr,
        )
        return 2
    else:
        llm = ScriptedLLM()
    if store is None or run_id is None:
        return _run(llm, prompt, mode=mode)
    writer = store.create_run(run_id, meta={"profile": profile or SCRIPTED_PROFILE, "mode": mode})
    print(f'Saving this run as "{validate_run_id(run_id)}".', file=sys.stderr)
    return _run(llm, prompt, writer, mode=mode)


def _resume(
    store: CheckpointStore, run_id: str, profile: str | None, requested_mode: Mode | None
) -> int:
    checkpoint, writer = store.resume_run(run_id)
    saved_mode = checkpoint.meta.get("mode", DEFAULT_MODE)
    if saved_mode not in MODES or (requested_mode is not None and requested_mode != saved_mode):
        writer.close()
        print(
            f'Run "{checkpoint.run_id}" was started in mode {saved_mode}; '
            "a resume keeps that mode (omit --mode).",
            file=sys.stderr,
        )
        return 2
    stored = checkpoint.meta.get("profile", SCRIPTED_PROFILE)
    if (profile or SCRIPTED_PROFILE) != stored:
        writer.close()
        hint = "omit --profile" if stored == SCRIPTED_PROFILE else f"pass --profile {stored}"
        print(
            f'Run "{checkpoint.run_id}" was started with profile {stored}; {hint}.', file=sys.stderr
        )
        return 2
    try:
        llm = _build_llm(None if stored == SCRIPTED_PROFILE else stored)
    except RouterConfigError as exc:
        writer.close()
        print(exc, file=sys.stderr)
        return 2
    return _run(llm, None, writer, checkpoint.snapshot, mode=saved_mode)


def _run(
    llm: LLM,
    prompt: str | None,
    writer: RunWriter | None = None,
    resume_from: LoopSnapshot | None = None,
    *,
    mode: Mode = DEFAULT_MODE,
) -> int:
    try:
        loop = AgentLoop(
            llm, [EchoTool()], context=ContextManager(), guard=build_guard(mode), checkpoint=writer
        )
        print(loop.run(prompt or "") if resume_from is None else loop.resume(resume_from))
    except (CheckpointError, ResumeBlocked) as exc:  # before AgentLoopError: no prefix
        print(exc, file=sys.stderr)
        return 1
    except AgentLoopError as exc:
        print(f"Agent failed: {exc}", file=sys.stderr)
        return 1
    except ProviderError as exc:
        print(f"Model call failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if writer is not None:
            writer.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
