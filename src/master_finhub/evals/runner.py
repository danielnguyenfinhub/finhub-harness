"""Benchmark runner: one isolated workspace per case, never raises, wall-clock cutoff via hook.

Patterns adapted (MIT, own code) from autogpt classic direct_benchmark runner.py:58 (fresh temp
workspace), :88-106 (timeout/exception -> failed result), evaluator.py:36,64 (dispatch on
eval type; timed-out never passes) and crewai experiment/runner.py:67-72 (stable id, per-case try).
Only `task` reaches the agent; `ground` (the answer key) never does.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from master_finhub.evals.verifiers import VERIFIERS, Grading
from master_finhub.runtime.context import ContextManager
from master_finhub.runtime.fake_llm import ScriptedLLM
from master_finhub.runtime.loop import LLM, AgentLoop, LoopSnapshot, Tool
from master_finhub.sandbox.workspace import Workspace
from master_finhub.tools.builtins.echo import EchoTool
from master_finhub.tools.safety import guard_tool_call


class _CutoffReached(Exception):
    pass


@dataclass(frozen=True)
class Benchmark:
    name: str
    task: str
    max_steps: int
    cutoff_s: float
    ground: dict[str, Any]
    case_id: str


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    name: str
    passed: bool
    score: float
    timed_out: bool
    error: str | None
    steps: int
    duration_s: float
    grading: Grading | None


@dataclass(frozen=True)
class SuiteReport:
    results: tuple[CaseResult, ...]
    passed: int
    failed: int
    total: int
    pass_rate: float


def _bad(path: object, field: str, want: str) -> ValueError:
    return ValueError(
        f'Benchmark {path}: field "{field}" must be {want}. Fix the benchmark JSON and retry.'
    )


def load_benchmark(path: str | os.PathLike[str]) -> Benchmark:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Benchmark {path}: cannot read ({type(exc).__name__}).") from None
    if not isinstance(data, dict):
        raise _bad(path, "<root>", "a JSON object")
    for key, typ, want in (
        ("name", str, "a string"),
        ("task", str, "a string"),
        ("max_steps", int, "an integer"),
        ("ground", dict, "an object"),
    ):
        if not isinstance(data.get(key), typ) or isinstance(data.get(key), bool):
            raise _bad(path, key, want)
    cutoff = data.get("cutoff_s")
    if (
        isinstance(cutoff, bool)
        or not isinstance(cutoff, (int, float))
        or not math.isfinite(cutoff)
        or cutoff < 0
    ):
        raise _bad(path, "cutoff_s", "a finite number, zero or more")
    ground = data["ground"]
    etype = ground.get("eval", {}).get("type") if isinstance(ground.get("eval"), dict) else None
    if (
        not isinstance(etype, str) or etype not in VERIFIERS
    ):  # A64: fail closed, no fallback verifier
        raise _bad(path, "ground.eval.type", f"one of {sorted(VERIFIERS)}")
    for key in ("files", "should_contain", "should_not_contain"):
        v = ground.get(key, [])
        if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
            raise _bad(path, f"ground.{key}", "a list of strings")
        if key != "files" and any(not s.strip() for s in v):
            raise _bad(path, f"ground.{key}", "a list of non-empty phrases")
    if not isinstance(ground.get("case_sensitive", True), bool):
        raise _bad(path, "ground.case_sensitive", "true or false")
    explicit = data.get("id")
    if explicit is not None and not isinstance(explicit, str):
        raise _bad(path, "id", "a string")
    canon = json.dumps({k: v for k, v in data.items() if k != "id"}, sort_keys=True)
    case_id = explicit or hashlib.sha256(canon.encode()).hexdigest()[:16]
    return Benchmark(data["name"], data["task"], data["max_steps"], float(cutoff), ground, case_id)


def _default_tools(_ws: Workspace) -> list[Tool]:
    return [EchoTool()]


def run_case(
    bench: Benchmark,
    llm_factory: Callable[[], LLM] = ScriptedLLM,
    tools_factory: Callable[[Workspace], list[Tool]] = _default_tools,
) -> CaseResult:
    start = time.monotonic()
    steps = 0
    timed_out = False
    error: str | None = None
    grading: Grading | None = None
    root: str | None = None
    try:

        def hook(snap: LoopSnapshot) -> None:
            nonlocal steps
            steps = max(steps, snap.step)
            if time.monotonic() >= start + bench.cutoff_s:
                raise _CutoffReached

        try:
            root = tempfile.mkdtemp(prefix="mf_eval_")
            ws = Workspace(root)
            loop = AgentLoop(
                llm_factory(),
                tools_factory(ws),
                bench.max_steps,
                context=ContextManager(),
                guard=guard_tool_call,
                checkpoint=hook,
            )
            parts = [loop.run(bench.task)]  # only the task reaches the agent
            parts += [ws.read_text(f) for f in bench.ground.get("files", [])]
            verifier = VERIFIERS[bench.ground["eval"]["type"]]
            grading = verifier("\n".join(parts), bench.ground)
        except _CutoffReached:
            timed_out, error = True, "timed out: cutoff_s reached"
        except Exception as exc:  # noqa: BLE001 - a case never raises (A53, A61)
            error = f"{type(exc).__name__}: {exc}"
    finally:
        if root is not None:
            shutil.rmtree(root, ignore_errors=True)
    ok = not timed_out and error is None and grading is not None
    ok = ok and grading is not None and grading.total > 0 and grading.failed == 0
    return CaseResult(
        case_id=bench.case_id,
        name=bench.name,
        passed=ok,
        score=grading.pass_rate if grading is not None and not timed_out else 0.0,
        timed_out=timed_out,
        error=error,
        steps=steps,
        duration_s=time.monotonic() - start,
        grading=grading,
    )


def run_suite(paths: Sequence[str | os.PathLike[str]], **kw: Any) -> SuiteReport:
    benches = [load_benchmark(p) for p in paths]
    seen: set[str] = set()
    for b in benches:
        if b.case_id in seen:
            raise ValueError(
                f'Suite has a duplicate case id "{b.case_id}". '
                "Give each benchmark a unique id (or remove the repeated file) and retry."
            )
        seen.add(b.case_id)
    results = tuple(run_case(b, **kw) for b in benches)
    passed = sum(r.passed for r in results)
    total = len(results)
    return SuiteReport(results, passed, total - passed, total, passed / total if total else 0.0)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="master_finhub.evals.runner")
    ap.add_argument("benchmarks", nargs="+")
    args = ap.parse_args(argv)
    try:
        report = run_suite(args.benchmarks)
    except ValueError as exc:
        print(str(exc))
        return 2
    print(json.dumps(asdict(report), indent=2))
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
