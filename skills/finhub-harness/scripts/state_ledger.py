"""Rebuild a harness state ledger from the files on disk and say where a run resumes.

Usage: state_ledger.py rebuild|resume PLAN [--base DIR] [--ledger FILE]. Run from the project root.
Exit 0 ok, start or resume; 3 stop (done, blocked or unreadable ledger); 2 bad plan or usage.
Rules R1-R9 are in skills/finhub-harness/references/state-ledger.md.
Field names adapted from references/meta_harness/.agents/skills/harness/SKILL.md:158 and
references/meta_harness/scripts/audit_harness.py:61 (Apache-2.0); a small state file rebuilt on
every change, from references/openharness/src/openharness/autopilot/service.py:405 (MIT); state
recomputed from durable records, and a reason kept while blocked, from
references/deepseek_harness/packages/goal/goal/src/fold.ts:339 and types.ts:64 (MIT).
The write through a temporary file and os.replace is adapted from
references/openharness/src/openharness/utils/fs.py:39 (MIT).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import re
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path, PurePosixPath, PureWindowsPath

PLAN_COLS = ("phase", "producer", "consumer", "path", "sections")
COLS = PLAN_COLS + ("completion", "note")
STATES = ("pending", "partial", "complete", "blocked")
Row = dict[str, str]
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
HEAD = re.compile(r"#{1,6}\s+(\S.*)")  # linear; the closing hashes are cut by rstrip, not a regex
HASH = re.compile(r"^plan-hash: ([0-9a-f]{12})\s*$", re.MULTILINE)
CAP = 8 * 1024 * 1024  # bytes read per phase file; a larger file reads as partial


def lines(text: str) -> Iterator[str]:
    """Lines outside code fences; a heading or table shown inside a fence is an example."""
    fence = ""
    for line in text.splitlines():
        m = FENCE.match(line)
        if fence:
            if m and m[1][0] == fence[0] and len(m[1]) >= len(fence) and not m[2].strip():
                fence = ""
        elif m:
            fence = m[1]
        else:
            yield line


def cells(line: str) -> list[str] | None:
    s = line.strip()
    if not s.startswith("|"):
        return None
    return [c.strip().strip("`") for c in s.strip("|").split("|")]


def table(text: str, cols: tuple[str, ...]) -> list[Row] | None:
    """Rows of the first table whose header is exactly `cols`; None when there is none."""
    it = lines(text)
    for line in it:
        if cells(line) != list(cols):
            continue
        if not set(next(it, "x").strip()) <= set("|-: "):
            raise ValueError("table header is not followed by a separator row")
        rows: list[Row] = []
        for row in it:
            c = cells(row)
            if c is None:
                break
            if len(c) != len(cols) or "" in c:
                raise ValueError(f"row needs {len(cols)} filled cells (use -): {row.strip()!r}")
            rows.append(dict(zip(cols, c, strict=True)))
        return rows
    return None


def heading(line: str) -> str | None:
    m = HEAD.match(line)
    return m[1].rstrip(" #\t") if m else None


def unique(rows: list[Row]) -> None:
    ids = [r["phase"] for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("phase ids must be unique")


def parse_plan(text: str) -> list[Row]:
    rows = table(text, PLAN_COLS)
    if rows is None:
        raise ValueError("no Handoff files table with columns " + " | ".join(PLAN_COLS))
    if len(rows) < 2:
        raise ValueError("a ledger needs at least two phases; a single phase has nothing to resume")
    unique(rows)
    for r in rows:
        p, w = PurePosixPath(r["path"]), PureWindowsPath(r["path"])
        if p.is_absolute() or w.anchor or ".." in p.parts or "\\" in r["path"]:
            raise ValueError(
                f"path must be relative, with no drive letter, UNC share or '..': {r['path']!r}"
            )
        if r["sections"] != "-" and "" in [s.strip() for s in r["sections"].split(";")]:
            raise ValueError(f"empty section name in {r['sections']!r}")
    return rows


def plan_hash(plan: list[Row]) -> str:
    text = "\n".join("|".join(p[c] for c in PLAN_COLS) for p in plan)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def contain(plan: list[Row], base: Path, ledger: Path) -> None:
    """Every phase file and the ledger must resolve inside base, symlinks followed."""
    root = base.resolve()
    for target in [base / p["path"] for p in plan] + [ledger]:
        try:
            inside = target.resolve().is_relative_to(root)
        except (OSError, ValueError, RuntimeError):
            inside = False
        if not inside:
            raise ValueError(f"resolves outside the project: {target}")


def parse_ledger(text: str) -> tuple[list[Row], str]:
    """(rows, plan hash) of a ledger; ValueError when it is not whole."""
    found = HASH.search(text)
    if found is None:
        raise ValueError("no plan-hash line")
    rows = table(text, COLS)
    if rows is None:
        raise ValueError("no ledger table with columns " + " | ".join(COLS))
    unique(rows)
    for r in rows:
        if r["completion"] not in STATES:
            raise ValueError(f"completion {r['completion']!r} is not one of {STATES}")
        if r["completion"] == "blocked" and r["note"] == "-":
            raise ValueError(f"phase {r['phase']} is blocked without a reason in note")
    return rows, found[1]


def judge(path: Path, sections: str) -> tuple[str, str]:
    """(completion, note) from one artefact: absent, empty or missing a section, or whole."""
    try:
        if not path.is_file():
            return "pending", "-"
        with path.open("rb") as f:
            raw = f.read(CAP + 1)
    except OSError as e:
        return "partial", f"unreadable: {e}"
    if len(raw) > CAP:
        return "partial", f"over the {CAP} byte limit"
    text = raw.decode("utf-8-sig", errors="replace")
    if not text.strip():
        return "partial", "empty file"
    have = {h for line in lines(text) if (h := heading(line)) is not None}
    need = [] if sections == "-" else [s.strip() for s in sections.split(";")]
    gone = [s for s in need if s not in have]
    return ("partial", "missing: " + ", ".join(gone)) if gone else ("complete", "-")


def rebuild(plan: list[Row], base: Path, old: list[Row] | None) -> list[Row]:
    """Ledger rows from the files; only a blocked row of the old ledger is carried over."""
    held = {r["phase"]: r["note"] for r in old or [] if r["completion"] == "blocked"}
    rows = []
    for p in plan:
        state, note = judge(base / p["path"], p["sections"])
        if state != "complete" and p["phase"] in held:
            state, note = "blocked", held[p["phase"]]
        rows.append({**p, "completion": state, "note": note})
    return rows


def save(path: Path, text: str) -> None:
    """Write through a temporary file in the same directory, then replace; a kill leaves either file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".00_state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def render(plan_path: str, digest: str, rows: list[Row]) -> str:
    nxt = next((r["phase"] for r in rows if r["completion"] != "complete"), "done")
    out = ["# State ledger", f"plan: {plan_path}", f"plan-hash: {digest}", f"next: {nxt}", ""]
    out += ["| " + " | ".join(COLS) + " |", "|" + "---|" * len(COLS)]
    for r in rows:
        out.append("| " + " | ".join(r[c] for c in COLS) + " |")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument("cmd", choices=("rebuild", "resume"))
    ap.add_argument("plan", help="file holding the Handoff files table")
    ap.add_argument("--base", default=".")
    ap.add_argument("--ledger", default="_workspace/00_state.md")
    a = ap.parse_args(argv)
    base, ledger = Path(a.base), Path(a.base) / a.ledger
    try:
        plan = parse_plan(Path(a.plan).read_text(encoding="utf-8"))
        contain(plan, base, ledger)
    except (OSError, ValueError) as e:
        print(f"ACTION: stop-no-plan\nREASON: {e}")
        return 2
    digest = plan_hash(plan)
    old: list[Row] | None = None
    changed = corrupt = False
    state = "absent"
    try:
        found = ledger.is_file()
    except OSError as e:  # a _workspace that cannot be searched: the ledger is unknown, not absent
        found, state, corrupt = False, f"unreadable: {e}", True
    if found:
        try:
            rows_old, h_old = parse_ledger(ledger.read_text(encoding="utf-8"))
            same = {r["phase"] for r in rows_old} == {p["phase"] for p in plan}
            if h_old == digest and not same:
                raise ValueError("its phases do not match the plan it names")
            old, state, changed = rows_old, "ok", h_old != digest
        except (OSError, ValueError) as e:
            state, corrupt = f"unreadable: {e}", True
    rows = rebuild(plan, base, None if changed else old)
    text = render(a.plan, digest, rows)
    try:
        try:
            current = ledger.read_text(encoding="utf-8", errors="replace")
        except OSError:
            current = None
        if current != text:
            save(ledger, text)
    except OSError as e:
        state = f"unwritable: {e}" if not corrupt else f"{state}; unwritable: {e}"
    unfinished = [r for r in rows if r["completion"] != "complete"]
    first = unfinished[0] if unfinished else None
    if a.cmd == "rebuild":
        print(f"LEDGER: {state}\nNEXT: {first['phase'] if first else 'done'}")
        return 0
    if first is None:
        act, why = "stop-done", "every phase is complete"
    elif corrupt:
        act, why = (
            "stop-unreadable",
            "a blocker may have been lost; ask the user, then resume again",
        )
    elif first["completion"] == "blocked":
        act, why = "stop-blocked", first["note"]
    else:
        act, why = ("resume" if first["completion"] == "partial" else "start"), first["note"]
    seen = {r["phase"]: r["completion"] for r in old or []}
    drift = ["plan changed, so no blocker is carried"] if changed else []
    drift += ["ledger unreadable, so any blocker is unknown"] if corrupt else []
    drift += [
        f"{r['phase']}: ledger {seen[r['phase']]}, files {r['completion']}"
        for r in rows
        if r["phase"] in seen and seen[r["phase"]] != r["completion"]
    ]
    drift += [
        f"{i}: in the ledger, not in the plan" for i in seen if i not in {p["phase"] for p in plan}
    ]
    after = rows[rows.index(first) + 1 :] if first else []
    print(f"LEDGER: {state}")
    print(f"ACTION: {act}\nPHASE: {first['phase'] if first else '-'}")
    print(f"PATH: {first['path'] if first else '-'}\nREASON: {why}")
    print("\n".join(f"DRIFT: {d}" for d in drift) or "DRIFT: -")
    print(
        "SUSPECT: " + (", ".join(r["phase"] for r in after if r["completion"] == "complete") or "-")
    )
    return 3 if act.startswith("stop") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
