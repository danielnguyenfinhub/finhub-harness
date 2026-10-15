"""Advisory scan of the packed plugin files for machine-specific or private values.

Usage: ship_scan.py [--locations-only] ZIP [ZIP ...]

The shipped set is read from each zip, so no include list lives here. Every file is either scanned
or skipped with a reason; a file that is neither makes coverage incomplete. A finding is a question
for the reader and never changes the exit code. Exit 0: scan ran, coverage complete. Exit 3:
coverage incomplete. Exit 2: operational error (bad argument, not a zip, import failure).
Repo-only: the packer does not ship this file, so it may import src/.

adapted from references/openrig/scripts/portability-report.mjs:25-52 (Apache-2.0); coverage
equality adapted from references/openrig/scripts/check-substance-gate.mjs:52-65 (Apache-2.0)
"""

from __future__ import annotations

import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final

MAX_BYTES: Final = 2 * 1024 * 1024  # a shipped text file larger than this is skipped with a reason
OWN_REPO: Final = "finhub-harness"  # the fork-url pattern ignores the plugin's own repository name

# Placeholder user names that are documentation, not a person (portability-report.mjs:35).
_PLACEHOLDER: Final = (
    r"(?:example|you|your-name|yourname|username|user|me|someone|name|x|test|tester|runner)"
)
# (category, pattern); credential is handled separately from the secret_scan rule table.
LINE_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "home-path",
        re.compile(
            rf"(?:/Users/|/home/)(?!{_PLACEHOLDER}/)[\w.-]+/"
            rf"|[A-Za-z]:\\Users\\(?!{_PLACEHOLDER}\\)[\w.-]+\\"
        ),
    ),
    (
        "machine-path",
        re.compile(r"/private/tmp/\S|/var/folders/[^/\s]+/|/tmp/claude-\d+"),
    ),
    (
        "network-address",
        re.compile(
            r"(?<![\w.])(?!(?:127\.|0\.0\.0\.0|255\.|192\.0\.2\.|198\.51\.100\.|203\.0\.113\.))"
            r"\d{1,3}(?:\.\d{1,3}){3}(?![\w.])"
            r"|(?<![\w.-])(?:[a-z0-9-]+\.)+(?:local|lan|internal|ts\.net|home\.arpa)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "email",
        re.compile(
            r"(?<![A-Za-z0-9._%+-])(?![A-Za-z0-9._%+-]*noreply)[A-Za-z0-9._%+-]+@"
            r"(?!(?:example|test|localhost)\b)(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}",
            re.IGNORECASE,
        ),
    ),
    (
        "fork-url",
        re.compile(rf"danielnguyenfinhub/(?!{OWN_REPO}(?![\w-]))[\w.-]+"),
    ),
)
CATEGORIES: Final = ("credential", *(c for c, _ in LINE_PATTERNS))


@dataclass(frozen=True)
class Finding:
    entry: str  # path inside the zip
    line: int  # 1-based
    category: str
    match: str  # matched text; for credential this is the rule id, never the secret


@dataclass(frozen=True)
class Coverage:
    shipped: tuple[str, ...]  # every non-directory entry, zip order, duplicates kept
    scanned: tuple[str, ...]
    skipped: tuple[tuple[str, str], ...]  # (entry, reason): binary | oversize | unreadable

    @property
    def missing(self) -> tuple[str, ...]:
        left = Counter(self.shipped) - Counter(self.scanned) - Counter(n for n, _ in self.skipped)
        return tuple(left.elements())

    @property
    def extra(self) -> tuple[str, ...]:
        accounted = Counter(self.scanned) + Counter(n for n, _ in self.skipped)
        return tuple((accounted - Counter(self.shipped)).elements())

    @property
    def complete(self) -> bool:
        return not self.missing and not self.extra


def _secret_spans(text: str) -> list[tuple[int, int, str]]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from master_finhub.tools.secret_scan import secret_spans

    return secret_spans(text)


def scan_text(text: str) -> list[tuple[int, str, str]]:
    """(line, category, match) for every hit. A credential's match is its rule id."""
    found: list[tuple[int, str, str]] = []
    for start, _end, rule in _secret_spans(text):
        found.append((text.count("\n", 0, start) + 1, "credential", rule))
    for number, line in enumerate(text.split("\n"), 1):
        for category, pattern in LINE_PATTERNS:
            for m in pattern.finditer(line):
                found.append((number, category, m.group(0)))
    return found


def normalise(entry: str) -> str:
    """The plugin zip holds skills/x/y; a skill zip holds x/y for the same file."""
    return entry.removeprefix("skills/")


def _scan_entry(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[str, object]:
    """("scanned", [(line, category, match)]) or ("skipped", reason)."""
    try:
        data = zf.open(info).read(MAX_BYTES + 1)  # the header size is not trusted
    except (zipfile.BadZipFile, RuntimeError, OSError, EOFError):
        return "skipped", "unreadable"
    if len(data) > MAX_BYTES:
        return "skipped", "oversize"
    if b"\x00" in data[:8192]:
        return "skipped", "binary"
    return "scanned", scan_text(data.decode("utf-8", errors="replace"))


def scan_zip(path: Path) -> tuple[Coverage, list[Finding]]:
    findings: list[Finding] = []
    scanned: list[str] = []
    skipped: list[tuple[str, str]] = []
    with zipfile.ZipFile(path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        shipped = tuple(i.filename for i in infos)
        for info in infos:
            kind, payload = _scan_entry(zf, info)
            # No else branch: any other state leaves the entry unaccounted and coverage says so.
            if kind == "scanned":
                scanned.append(info.filename)
                assert isinstance(payload, list)
                findings += [Finding(info.filename, ln, cat, m) for ln, cat, m in payload]
            elif kind == "skipped":
                skipped.append((info.filename, str(payload)))
    return Coverage(shipped, tuple(scanned), tuple(skipped)), findings


def render(
    results: list[tuple[Path, Coverage, list[Finding]]], *, locations_only: bool = False
) -> str:
    out = ["SHIP-SCAN (advisory): findings are questions, not verdicts, and never fail the build"]
    complete, problems = True, []
    merged: dict[tuple[str, int, str], tuple[str, str, list[str]]] = {}
    for path, cov, found in results:
        out.append(
            f"{path}: scanned {len(cov.scanned)} of {len(cov.shipped)} shipped files, "
            f"skipped {len(cov.skipped)}"
        )
        out += [f"SKIPPED {path}:{name} ({why})" for name, why in cov.skipped]
        if not cov.complete:
            complete = False
            problems.append(
                f"{path}: missing {', '.join(cov.missing) or '-'}; "
                f"extra {', '.join(cov.extra) or '-'}"
            )
        for f in found:
            key = (normalise(f.entry), f.line, f.category)
            merged.setdefault(key, (f.entry, f.match, []))[2].append(str(path))
    out.append(
        "COVERAGE: COMPLETE" if complete else f"COVERAGE: INCOMPLETE ({'; '.join(problems)})"
    )
    credential_lines = {(p, ln) for p, ln, cat in merged if cat == "credential"}
    out.append(f"FINDINGS: {len(merged)} location(s)")
    if not merged:
        out[-1] += (
            " (not a clean bill: only credential, home-path, machine-path, network-address, "
            "email and fork-url shapes were looked for)"
        )
    for category in CATEGORIES:
        rows = sorted(k for k in merged if k[2] == category)
        if not rows:
            continue
        out.append(f"## {category} ({len(rows)})")
        for key in rows:
            entry, match, zips = merged[key]
            where = f"{entry}:{key[1]}"
            if category == "credential":
                what = f" credential rule {match}"
            elif locations_only or (key[0], key[1]) in credential_lines:
                what = ""
            else:
                what = f" matched `{match}`"
            out.append(f"- {where}{what} [{', '.join(zips)}]")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    locations_only = "--locations-only" in args
    paths = [Path(a) for a in args if a != "--locations-only"]
    if not paths:
        print("usage: ship_scan.py [--locations-only] ZIP [ZIP ...]", file=sys.stderr)
        return 2
    try:
        _secret_spans("")
    except ImportError as exc:
        print(f"ship_scan: cannot import master_finhub.tools.secret_scan: {exc}", file=sys.stderr)
        return 2
    results: list[tuple[Path, Coverage, list[Finding]]] = []
    for path in paths:
        try:
            cov, found = scan_zip(path)
        except (OSError, zipfile.BadZipFile) as exc:
            print(f"ship_scan: {path}: {exc}", file=sys.stderr)
            return 2
        results.append((path, cov, found))
    print(render(results, locations_only=locations_only))
    return 0 if all(cov.complete for _, cov, _ in results) else 3


if __name__ == "__main__":
    try:
        code = main()
        if sys.stdout is not None:  # closed with >&-: print did nothing, so flush has nothing
            sys.stdout.flush()
    except BrokenPipeError:  # the reader hung up (| head -1): not a fault of ours
        sys.stdout = None  # so the exit-time flush cannot fail again
        code = 141  # 128 + SIGPIPE, the status a shell reports for a writer whose pipe closed
    sys.exit(code)
