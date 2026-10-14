"""Check which rigor level a unit of work runs at, and that its reports and its commit say so.

Usage:
  rigor_check.py check ORCHESTRATOR LEDGER UNIT PREV CHANGED [REPORT ...]

ORCHESTRATOR holds a `## Rigor` section with one table: `| scope | class | level | assigned-by | on |`
(quality-gates.md section 3-10). A class is `audited-decision` (gated, preselected) or `other` (light by
default; gated only when the owner assigns it). UNIT is `<scope>/<item>`: a row of the table and one piece of
work. LEDGER is the waiver ledger of section 3-9, or `-` for a harness that never downgrades. PREV is the
previous committed copy of ORCHESTRATOR (for example `git show HEAD:<path>` written to a file), or `-` when
there is none (the first commit). CHANGED is a file that lists the paths this commit changes, one per line,
relative to the repository root, written by the caller.

A unit runs `light` when its table row is `other, light`, or when an active ledger row has the scope
`rigor:<scope>/<item>` (granted <= today <= expires). Lowering a row of the table against PREV (a class from
audited-decision to other, a level from gated to light, a scope removed, a new scope classed as other) needs an
active ledger row `rigor:<scope>/table`. A typed owner name alone never lowers anything.

Exit 0: clean. Exit 4: at least one refusal, one line per problem, FILE:LINE: message. Exit 2: bad call (any
option other than a single `-` for LEDGER or PREV, a missing argument, an unreadable file, no table). There is
no option that sets the clock or relaxes a rule. Standard library only, no network, no subprocess; it imports
waiver_ledger.py from its own directory and restates none of its rules.

adapted from references/openrig/docs/reference/sdlc-conventions.md:20-24 (Apache-2.0): the default is the
assigned flow, and an agent cannot raise or lower it for itself. adapted from
references/openrig/packages/daemon/specs/agents/shared/skills/pods/orchestration-team/SKILL.md:149-152
(Apache-2.0): only the owner's assignment admits or lifts a gate, and the decision is written down. The table,
the ledger-row receipt, the comparison with the previous table, the effective-level computation and the
report-line check are NET-NEW.
"""

from __future__ import annotations

import posixpath
import re
import sys
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import waiver_ledger as wl

USAGE = (
    "usage: rigor_check.py check ORCHESTRATOR LEDGER UNIT PREV CHANGED [REPORT ...]"
    "   (LEDGER and PREV may be -)"
)
TABLE = ("scope", "class", "level", "assigned-by", "on")
CLASSES = ("audited-decision", "other")
LEVELS = ("light", "gated")
SCOPE = re.compile(r"[a-z0-9][a-z0-9._-]{0,47}")
UNIT = re.compile(r"([a-z0-9][a-z0-9._-]{0,47})/([A-Za-z0-9][A-Za-z0-9._-]{0,63})")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*$|^\s*(`{3,}|~{3,})\S")
HEADING = re.compile(r"^## Rigor\s*$")
HEAD_LINES = 8
TABLE_ITEM = "table"  # the reserved item of a receipt row that lowers a row of the table

Row = tuple[str, str, str, str]  # class, level, assigned-by, on


class Usage(Exception):
    pass


def unfenced(lines: Sequence[str]) -> list[tuple[int, str]]:
    """(line number, text) of every line outside a code fence; a fence line itself is dropped."""
    out: list[tuple[int, str]] = []
    mark = ""
    for n, raw in enumerate(lines, 1):
        m = FENCE.match(raw)
        if m:
            token = m.group(1) or m.group(2)
            if not mark:
                mark = token
            elif token[0] == mark[0] and len(token) >= len(mark) and m.group(1):
                mark = ""
            continue
        if not mark:
            out.append((n, raw))
    return out


def rank(cls: str, level: str) -> int:
    """2 for audited-decision, 1 for an `other` unit that is gated, 0 for an `other` unit that is light."""
    if cls == "audited-decision":
        return 2
    return 1 if level == "gated" else 0


def read_table(name: str, text: str, today: date) -> tuple[dict[str, Row], list[str]]:
    rows: dict[str, Row] = {}
    bad: list[str] = []
    sections = 0
    inside = False
    header = False
    for n, raw in unfenced(text.splitlines()):
        line = raw.strip()
        if HEADING.match(raw):
            sections += 1
            inside = True
            if sections == 2:
                bad.append(f"{name}:{n}: more than one ## Rigor section")
            continue
        if raw.startswith("## "):
            inside = False
            continue
        if not inside or not line.startswith("|"):
            continue
        parts = wl.split(line)
        if parts == list(TABLE):
            if header:
                bad.append(f"{name}:{n}: second table in the Rigor section")
            header = True
        elif not header:
            raise Usage(
                f"{name}:{n}: the first table line must be the header: | "
                + " | ".join(TABLE)
                + " |"
            )
        elif parts and all(wl.SEPARATOR.fullmatch(p) for p in parts):
            continue
        elif len(parts) != len(TABLE):
            bad.append(
                f"{name}:{n}: rigor table: expected {len(TABLE)} cells between pipes, got {len(parts)}"
            )
        else:
            scope, cls, level, by, on = parts
            if not all(parts):
                bad.append(f"{name}:{n}: rigor table: blank cell")
                continue
            if not SCOPE.fullmatch(scope):
                bad.append(f"{name}:{n}: scope must match {SCOPE.pattern}")
            if scope in rows:
                bad.append(f"{name}:{n}: rigor table: repeated scope {scope}")
            if cls not in CLASSES:
                bad.append(f"{name}:{n}: class must be one of: {', '.join(CLASSES)}")
            if level not in LEVELS:
                bad.append(f"{name}:{n}: level must be light or gated")
            owner = by.removeprefix("owner:") if by.startswith("owner:") else ""
            if by != "default" and owner not in wl.OWNERS:
                bad.append(
                    f"{name}:{n}: assigned-by must be default or owner:<name> with <name> one of: "
                    + ", ".join(wl.OWNERS)
                )
            if cls == "audited-decision" and level == "light":
                bad.append(
                    f"{name}:{n}: audited-decision output cannot be assigned light in the table"
                )
            if cls == "other" and by == "default":
                bad.append(f"{name}:{n}: class other must be assigned by owner:<name>, not default")
            d = wl.day(on)
            if d is None:
                bad.append(f"{name}:{n}: on must be a calendar date YYYY-MM-DD")
            elif d > today + timedelta(days=wl.SLACK_DAYS):
                bad.append(f"{name}:{n}: on is more than {wl.SLACK_DAYS} day after today")
            rows[scope] = (cls, level, by, on)
    if not header:
        raise Usage(
            f"{name}: no Rigor table (a ## Rigor section with | " + " | ".join(TABLE) + " |)"
        )
    return rows, bad


def active(r: dict[str, str], today: date) -> bool:
    start, end = wl.day(r["granted"]), wl.day(r["expires"])
    return bool(start and end and start <= today <= end)


def read_downgrades(
    name: str, text: str, scopes: set[str], today: date
) -> tuple[dict[str, tuple[dict[str, str], int]], list[str]]:
    """Ledger rows whose scope starts `rigor:`, keyed by `<scope>/<item>`; the ledger's own row rules apply."""
    found: dict[str, tuple[dict[str, str], int]] = {}
    bad: list[str] = []
    header = False
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        parts = wl.split(line)
        if parts == list(wl.COLUMNS):
            header = True
            continue
        if not header or (parts and all(wl.SEPARATOR.fullmatch(p) for p in parts)):
            continue
        if len(parts) != len(wl.COLUMNS) or not parts[1].startswith("rigor:"):
            continue
        r = dict(zip(wl.COLUMNS, parts, strict=True))
        bad.extend(f"{name}:{n}: {p}" for p in wl.row_problems(r, today))
        target = r["scope"][len("rigor:") :]
        m = UNIT.fullmatch(target)
        if not m or m.group(1) not in scopes:
            bad.append(f"{name}:{n}: downgrade waiver names no scope and item of the Rigor table")
        else:
            found[target] = (r, n)
    if not header:
        raise Usage(f"{name}: no ledger table (header: | " + " | ".join(wl.COLUMNS) + " |)")
    return found, bad


def check_report(name: str, text: str, expect: str) -> tuple[bool, list[str]]:
    """(is a passing QA report, problems) for one report read against the line RIGOR must carry."""
    lines = text.splitlines()
    first = lines[0] if lines else ""
    qa = first.startswith("RESULT:")
    if not (qa or first.startswith("TOTALS:")):
        return False, [f"{name}:1: report first line is not RESULT: or TOTALS:"]
    problems: list[str] = []
    if qa and first != "RESULT: PASS":
        problems.append(f"{name}:1: QA report is not RESULT: PASS")
    head = [t for _, t in unfenced(lines[:HEAD_LINES]) if t.startswith("RIGOR:")]
    if not head:
        problems.append(f"{name}:1: report has no RIGOR line in its first {HEAD_LINES} lines")
    elif len(head) > 1:
        problems.append(f"{name}:1: report has more than one RIGOR line")
    elif head[0] != expect:
        problems.append(f"{name}:1: RIGOR line does not match the table row (expected `{expect}`)")
    return qa and first == "RESULT: PASS", problems


def norm(path: str) -> str:
    return posixpath.normpath(path.strip().replace("\\", "/"))


def check_text(
    orch_name: str,
    orch: str,
    ledger_name: str,
    ledger: str | None,
    unit: str,
    prev: str | None,
    changed: Sequence[str],
    reports: Sequence[tuple[str, str]],
    today: date,
) -> tuple[int, list[str]]:
    rows, bad = read_table(orch_name, orch, today)
    downgrades: dict[str, tuple[dict[str, str], int]] = {}
    before: dict[str, Row] | None = None
    if prev is not None:
        try:
            before, _ = read_table("PREV", prev, today)
        except Usage:
            before = None  # a previous file with no table: the table is being introduced
    if ledger is not None:
        # a receipt may name a scope the new table no longer lists (a removed scope)
        scopes = set(rows) | set(before or ())
        downgrades, more = read_downgrades(ledger_name, ledger, scopes, today)
        bad.extend(more)
    out = [f"TODAY: {today.isoformat()}"]
    paths = {norm(p) for p in changed if p.strip()}
    if before is not None:
        for scope, (cls, level, by, on) in rows.items():
            was = (
                rank(*before[scope][:2]) if scope in before else 2
            )  # an unlisted scope is audited-decision
            now = rank(cls, level)
            if now >= was:
                continue
            was_name = (
                "audited-decision" if was == 2 else ("other, gated" if was == 1 else "other, light")
            )
            row = downgrades.get(f"{scope}/{TABLE_ITEM}")
            if row and active(row[0], today):
                out.append(
                    f"LOWERED: {scope} {was_name} -> {cls}, {level} by {row[0]['owner']}, "
                    f"waiver {row[0]['id']} expires {row[0]['expires']}"
                )
            else:
                bad.append(
                    f"{orch_name}: {scope}: {was_name} -> {cls}, {level} lowers rigor and needs an "
                    f"active receipt row rigor:{scope}/{TABLE_ITEM}"
                )
        for scope in before:
            if scope not in rows:
                row = downgrades.get(f"{scope}/{TABLE_ITEM}")
                if row and active(row[0], today):
                    out.append(
                        f"LOWERED: {scope} removed from the Rigor table by {row[0]['owner']}, "
                        f"waiver {row[0]['id']} expires {row[0]['expires']}"
                    )
                else:
                    bad.append(
                        f"{orch_name}: {scope}: scope removed from the Rigor table lowers rigor and "
                        f"needs an active receipt row rigor:{scope}/{TABLE_ITEM}"
                    )
        if ledger is not None and norm(orch_name) in paths and norm(ledger_name) in paths:
            bad.append(
                f"{orch_name}: the Rigor table and the ledger change in one commit; "
                "the receipt row is committed first, by a unit of its own"
            )
    m = UNIT.fullmatch(unit)
    if not m:
        bad.append(f"{orch_name}: unit must be <scope>/<item>, got {unit!r}")
    elif m.group(1) not in rows:
        bad.append(f"{orch_name}: unit is not a scope in the Rigor table: {m.group(1)}")
    elif m.group(2) == TABLE_ITEM:
        bad.append(f"{orch_name}: the item name {TABLE_ITEM!r} is reserved for table receipts")
    if bad or not m or m.group(1) not in rows:
        out.extend(bad)
        out.append("STATE: RED")
        return 4, out
    cls, base, by, on = rows[m.group(1)]
    level = base
    note = f"class {cls}, assigned-by {by} on {on}"
    if base == "gated" and unit in downgrades:
        r, _ = downgrades[unit]
        start = wl.day(r["granted"])
        if active(r, today):
            level = "light"
            note += f"; downgrade waiver {r['id']} by {r['owner']}, expires {r['expires']}"
            out.append(
                f"DOWNGRADE: {unit} runs light (no judge, no QA agent) by {r['owner']}, "
                f"waiver {r['id']} expires {r['expires']}"
            )
        elif start and start > today:
            out.append(
                f"NOTICE: downgrade waiver {r['id']} is not active until {r['granted']}; the unit runs gated"
            )
        else:
            out.append(
                f"NOTICE: downgrade waiver {r['id']} expired on {r['expires']}; the unit runs gated"
            )
    out.insert(1, f"EFFECTIVE: {unit} {level} ({note})")
    if level == "light" and ledger is not None and norm(ledger_name) in paths:
        bad.append(f"{ledger_name}: a light unit must not change the ledger")
    if level == "gated":
        expect = f"RIGOR: gated unit={unit} by={by} on={on}"
        have_qa = False
        for name, text in reports:
            is_qa, problems = check_report(name, text, expect)
            have_qa = have_qa or is_qa
            bad.extend(problems)
        if not have_qa:
            bad.append(
                f"{orch_name}: gated unit has no QA report (a report whose first line is RESULT: PASS)"
            )
    out.extend(bad)
    out.append("STATE: RED" if bad else "STATE: CLEAN")
    return (4 if bad else 0), out


def main(argv: list[str], today: date | None = None) -> int:
    args = argv[1:]
    if len(args) < 6 or args[0] != "check" or any(a.startswith("-") and a != "-" for a in args):
        print(USAGE, file=sys.stderr)
        return 2
    try:
        orch = Path(args[1]).read_bytes().decode("utf-8")
        ledger = None if args[2] == "-" else Path(args[2]).read_bytes().decode("utf-8")
        prev = None if args[4] == "-" else Path(args[4]).read_bytes().decode("utf-8")
        changed = Path(args[5]).read_bytes().decode("utf-8").splitlines()
        reports = [(p, Path(p).read_bytes().decode("utf-8")) for p in args[6:]]
        day = today or datetime.now().astimezone().date()
        code, lines = check_text(
            args[1], orch, args[2], ledger, args[3], prev, changed, reports, day
        )
    except (OSError, UnicodeDecodeError) as e:
        print(f"rigor_check: cannot read an input: {e}", file=sys.stderr)
        return 2
    except Usage as e:
        print(f"rigor_check: {e}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
