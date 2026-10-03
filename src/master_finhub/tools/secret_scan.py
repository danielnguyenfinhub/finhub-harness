"""Secret-shape redaction for tool results and MCP text: returns rule labels, never the match.

Rule table adapted from references/openharness/src/openharness/memory/team.py:24 (MIT) and
references/openhands/src/utils/redact-mcp-secrets.ts:18 (MIT); Bearer keeps its prefix (:31).
Anchored token shapes only: no generic hex, entropy or ``password=`` assignment rule.
Spans are found on the original text and merged, so overlapping matches never leave a fragment.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

_TOKEN: Final = r"[A-Za-z0-9._~+/=-]"
Span = tuple[int, int, str]  # start, end, rule id or replacement text

# re.ASCII on every rule: with Unicode ``\b`` a key glued to é or CJK text was missed.
# Table order breaks ties: when two matches start together the earlier rule names the span.
# (rule id, pattern, token must contain an ASCII digit); the digit test is done in Python
# because a look-ahead inside the pattern made the scan quadratic. R10 starts after a
# look-behind, not \b: ``-`` is both a boundary and a segment character, so ``\b`` let
# every ``-eyJ`` in one run start a scan to the end of that run.
RULES: Final[tuple[tuple[str, re.Pattern[str], bool], ...]] = (
    (
        "private-key",
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY(?: BLOCK)?-----.*?"
            r"(?:-----END [A-Z ]*PRIVATE KEY(?: BLOCK)?-----|\Z)",
            re.DOTALL | re.ASCII,
        ),
        False,
    ),
    (
        "bearer-token",
        re.compile(rf"(?P<keep>\bBearer\s+[\"']?){_TOKEN}{{16,}}", re.IGNORECASE | re.ASCII),
        False,
    ),
    (
        "mercury-mcp-key",
        re.compile(
            rf"(?P<keep>\bx-mcp-key[\"']?\s*[:=]\s*[\"']?){_TOKEN}{{8,}}", re.IGNORECASE | re.ASCII
        ),
        False,
    ),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", re.ASCII), False),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b", re.ASCII), False),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", re.ASCII), False),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b", re.ASCII), False),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b", re.ASCII), True),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}", re.ASCII), False),
    (
        "jwt",
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b",
            re.ASCII,
        ),
        False,
    ),
)
_DIGIT: Final = re.compile(r"[0-9]")


def secret_spans(text: str) -> list[Span]:
    """(start, end, rule id) of every rule match in ``text``, in table order; prefixes excluded."""
    found: list[Span] = []
    for rule, pattern, need_digit in RULES:
        for m in pattern.finditer(text):
            start = m.end("keep") if "keep" in pattern.groupindex else m.start()
            if not need_digit or _DIGIT.search(text, start, m.end()):
                found.append((start, m.end(), rule))
    return found


def merge_spans(spans: Iterable[Span]) -> list[Span]:
    """Union overlapping spans; a merged span keeps the earliest start's tag (ties: input order)."""
    merged: list[Span] = []
    for start, end, tag in sorted(spans, key=lambda span: span[0]):
        if merged and start < merged[-1][1]:
            first, last, kept = merged[-1]
            merged[-1] = (first, max(last, end), kept)
        else:
            merged.append((start, end, tag))
    return merged


def apply_spans(text: str, merged: Iterable[Span]) -> str:
    """Replace each merged span with its tag."""
    out: list[str] = []
    pos = 0
    for start, end, tag in merged:
        out += (text[pos:start], tag)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def redact_secrets(text: str) -> tuple[str, tuple[str, ...]]:
    """Replace every rule match with ``[REDACTED:<rule>]``; return (text, rules that fired)."""
    merged = merge_spans(secret_spans(text))
    fired = {rule for _, _, rule in merged}
    out = apply_spans(text, ((s, e, f"[REDACTED:{rule}]") for s, e, rule in merged))
    return out, tuple(rule for rule, _, _ in RULES if rule in fired)
