"""Deterministic string-match verifier. No LLM judge, no execution of agent-written code.

Check semantics adapted from autogpt classic direct_benchmark evaluator.py:103-109 (MIT);
grading schema from revfactory skill-testing-guide.md:143-155. A code-running verifier must
go through slice 8 DockerEngine and needs its own design row (A57).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

EVIDENCE_MAX = 200


@dataclass(frozen=True)
class Expectation:
    text: str
    passed: bool
    evidence: str  # what was actually found, <= EVIDENCE_MAX chars, never the whole output


@dataclass(frozen=True)
class Grading:
    expectations: tuple[Expectation, ...]
    passed: int
    failed: int
    total: int
    pass_rate: float  # passed / total; 0.0 when total == 0


Verifier = Callable[[str, Mapping[str, Any]], Grading]


def grade(expectations: list[Expectation]) -> Grading:
    passed = sum(e.passed for e in expectations)
    total = len(expectations)
    return Grading(
        tuple(expectations), passed, total - passed, total, passed / total if total else 0.0
    )


def contains(content: str, ground: Mapping[str, Any]) -> Grading:
    fold = not ground.get("case_sensitive", True)
    hay = content.casefold() if fold else content
    snippet = content[:EVIDENCE_MAX]
    out: list[Expectation] = []
    for phrase in ground.get("should_contain", []):
        ok = (phrase.casefold() if fold else phrase) in hay
        out.append(Expectation(f'output contains "{phrase}"', ok, "found" if ok else snippet))
    for phrase in ground.get("should_not_contain", []):
        bad = (phrase.casefold() if fold else phrase) in hay
        out.append(Expectation(f'output lacks "{phrase}"', not bad, snippet if bad else "absent"))
    return grade(out)


VERIFIERS: Final[Mapping[str, Verifier]] = {"contains": contains}
