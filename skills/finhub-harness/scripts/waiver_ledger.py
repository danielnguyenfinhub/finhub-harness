"""Check the waiver ledger: every accepted gap has an owner, a receipt and an expiry, and an expired one is red.

Usage:
  waiver_ledger.py check LEDGER

LEDGER is a markdown file holding one table with the columns in COLUMNS (quality-gates.md section 3-9).
Exit 0: every row is valid and none has expired (each active waiver is named in the output). Exit 4: at
least one row is refused or has expired; one line per problem, LEDGER:LINE: message. Exit 2: bad call
(any option, an unreadable file, no table). There is no option that sets the clock or relaxes a rule;
the date is the process's local date, so the process time zone is the one clock input. Standard library only; no network, no subprocess; it reads the one file.

A waiver does not change a verdict. It records that the owner accepted a named gap, when, on whose
words, and when it comes back. An invalid ledger is a loud failure, never a silent pass.

adapted from references/openrig/scripts/gate-lane-ledger.mjs:14-112 (Apache-2.0): the five fields
(a suite, a reason, a receipt, an owner, an expiry), the calendar-date test, the ceiling on the expiry,
expiry as a mechanical red, and naming every exclusion in the output. Rewritten in Python for a
markdown table; the owner list, the dated receipt and the 90-day ceiling are NET-NEW (OR-S6).
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path

USAGE = "usage: waiver_ledger.py check LEDGER"
OWNERS = ("daniel",)  # the human owners; one line to change in a copy for another harness
MAX_DAYS = 90  # the longest a waiver lives from `granted`; renew with a new receipt
SLACK_DAYS = 1  # a grant may be dated this many days ahead of the machine's date (clock skew)
SOON_DAYS = 14  # a notice (not red) this many days before expiry
COLUMNS = ("id", "scope", "gap", "owner", "receipt", "granted", "expires")
ID = re.compile(r"[A-Z][A-Z0-9-]{2,31}")
DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
RECEIPT = re.compile(r'(?:words: "[^"]+"|pr: \S+)(?: .*)? ([0-9]{4}-[0-9]{2}-[0-9]{2})')
SEPARATOR = re.compile(r":?-{3,}:?")


class Usage(Exception):
    pass


def day(value: str) -> date | None:
    if not DAY.fullmatch(value):
        return None
    try:
        return date(int(value[:4]), int(value[5:7]), int(value[8:]))
    except ValueError:
        return None


def split(line: str) -> list[str]:
    """The cells of a table line; a line that does not end in a pipe has none, so it is refused."""
    if len(line) < 2 or not line.endswith("|"):
        return []
    return [c.strip() for c in line[1:-1].split("|")]


def row_problems(r: dict[str, str], today: date) -> list[str]:
    out = [f"missing {c}" for c in COLUMNS if not r[c]]
    if r["id"] and not ID.fullmatch(r["id"]):
        out.append("id must match [A-Z][A-Z0-9-]{2,31}")
    if r["owner"] and r["owner"] not in OWNERS:
        out.append(f"owner must be one of: {', '.join(OWNERS)}")
    start, end = day(r["granted"]), day(r["expires"])
    if r["granted"] and start is None:
        out.append("granted must be a calendar date YYYY-MM-DD")
    if r["expires"] and end is None:
        out.append("expires must be a calendar date YYYY-MM-DD")
    if start and start > today + timedelta(days=SLACK_DAYS):
        out.append(f"granted {r['granted']} is more than {SLACK_DAYS} day after today")
    if start and end:
        if end < start:
            out.append("expires is before granted")
        elif (end - start).days > MAX_DAYS:
            out.append(f"lifetime {(end - start).days} days exceeds ceiling {MAX_DAYS}")
    if r["receipt"]:
        m = RECEIPT.fullmatch(r["receipt"])
        if not m:
            out.append('receipt must be words: "<reply>" YYYY-MM-DD or pr: <ref> YYYY-MM-DD')
        elif m.group(1) != r["granted"]:
            out.append(f"receipt date {m.group(1)} differs from granted {r['granted']}")
    return out


def check_text(name: str, text: str, today: date) -> tuple[int, list[str]]:
    rows: list[tuple[int, dict[str, str]]] = []
    bad: list[str] = []
    header = False
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        parts = split(line)
        if not header:
            if parts != list(COLUMNS):
                raise Usage(
                    f"{name}:{n}: the first table line must be the header: | "
                    + " | ".join(COLUMNS)
                    + " |"
                )
            header = True
        elif parts and all(SEPARATOR.fullmatch(p) for p in parts):
            continue
        elif len(parts) != len(COLUMNS):
            bad.append(f"{name}:{n}: expected {len(COLUMNS)} cells between pipes, got {len(parts)}")
        else:
            rows.append((n, dict(zip(COLUMNS, parts))))
    if not header:
        raise Usage(f"{name}: no ledger table (header: | " + " | ".join(COLUMNS) + " |)")
    seen: set[str] = set()
    active: list[tuple[int, dict[str, str]]] = []
    expired = 0
    notices: list[str] = []
    for n, r in rows:
        problems = row_problems(r, today)
        if r["id"] in seen:
            problems.append(f"duplicate id {r['id']}")
        seen.add(r["id"])
        bad.extend(f"{name}:{n}: {p}" for p in problems)
        end = day(r["expires"])
        if end is not None and end < today:
            expired += 1
            bad.append(
                f"{name}:{n}: EXPIRED: {r['id']} expired on {r['expires']} ({(today - end).days} day(s) ago);"
                " renew with the owner's new words or close the gap"
            )
        elif not problems:
            active.append((n, r))
            if end is not None and (end - today).days <= SOON_DAYS:
                notices.append(f"NOTICE: {r['id']} expires in {(end - today).days} day(s)")
    out = [f"TODAY: {today.isoformat()}"]
    if active:
        out.append(
            f"WAIVERS: {len(active)} active, {expired} expired, {len(bad) - expired} other problem(s) (each is named)"
        )
        out.extend(
            f"  {r['id']} owner {r['owner']} expires {r['expires']} ({r['scope']})"
            for _, r in active
        )
    else:
        out.append(
            f"WAIVERS: 0 active, {expired} expired, {len(bad) - expired} other problem(s) (no exclusions)"
        )
    out.extend(notices)
    out.extend(bad)
    out.append("STATE: RED" if bad else "STATE: CLEAN")
    return (4 if bad else 0), out


def main(argv: list[str], today: date | None = None) -> int:
    if len(argv) != 3 or argv[1] != "check" or argv[2].startswith("-"):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        text = Path(argv[2]).read_bytes().decode("utf-8")
        code, lines = check_text(argv[2], text, today or date.today())
    except (OSError, UnicodeDecodeError) as e:
        print(f"waiver_ledger: cannot read {argv[2]}: {e}", file=sys.stderr)
        return 2
    except Usage as e:
        print(f"waiver_ledger: {e}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    try:
        code = main(sys.argv)
        if sys.stdout is not None:  # closed with >&-: print did nothing, so flush has nothing
            sys.stdout.flush()
    except BrokenPipeError:  # the reader hung up (| head -1): not a fault of ours
        sys.stdout = None  # so the exit-time flush cannot fail again
        code = 141  # 128 + SIGPIPE, the status a shell reports for a writer whose pipe closed
    sys.exit(code)
