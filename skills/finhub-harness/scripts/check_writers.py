"""Check the `## Writers` tables of a generated orchestrator: ownership labels and overlap.

Usage: check_writers.py [--require] FILE.md [FILE.md ...]
Exit 0 = no violations, 1 = at least one, 2 = usage or unreadable file. The rules W1-W10 are
listed in references/write-safety.md. Columns are read by header name, so their order is free.
Fenced blocks are skipped, so the worked examples in that reference do not count. Do not run it
on that reference or any other file that only describes the rules: it reports them as W6 lines.

The label set and the rule that advisory ownership is never called exclusive are adapted from
references/meta_harness/.agents/skills/harness/SKILL.md:133 (Apache-2.0); the order of the
ladder and the overlap and lowering rules from
references/meta_harness/docs/architecture/runtime-capabilities.md:46 (Apache-2.0).
Rewritten, not copied.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

LABELS = ("enforced", "workspace-enforced", "advisory", "serialised")  # highest rung first
RULES = {
    "W1": "Label and Wanted are each one of the four labels.",
    "W2": "`enforced` or `advisory` writers in one batch have disjoint Writes.",
    "W3": "A `serialised` writer is alone in its batch.",
    "W4": "`enforced` and `workspace-enforced` writers name their mechanism.",
    "W5": "A Label on a lower rung than Wanted says why.",
    "W6": (
        "No line that says `advisory` calls ownership exclusive, locked or guaranteed, "
        'unless "not" or "never" comes within the six words before that word.'
    ),
    "W7": (
        "The table has the six columns, at least one row, no blank line inside it, "
        "a whole-number Batch and a Role on every row."
    ),
    "W8": "With `--require`, the file has a Writers table.",
    "W9": (
        "A Role that says per or each item, file or instance, or N instances, "
        "has a `<item>` part or a glob in every Writes path."
    ),
    "W10": "A table has at most 50 rows, and a Writes cell at most 500 characters and 10 paths.",
}
NEGATION_WINDOW = 6  # the six words in the W6 rule
MAX_ROWS, MAX_CELL, MAX_PATHS = 50, 500, 10  # the caps in W10
COLUMNS = ("batch", "role", "writes", "label", "wanted", "mechanism")
HEADING = re.compile(r"^#{2,4}\s+(\S.*)$")
ANY_HEADING = re.compile(r"^\s{0,3}#{1,6}(\s|$)")
UNKNOWN_PATH = re.compile(r"""[\s`"';()#:]|<br""")  # an annotated or quoted part, or a drive letter
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
OVERCLAIM = re.compile(r"\b(exclusive(ly)?|locked?|guarantee[ds]?)\b", re.IGNORECASE)
NEGATION = re.compile(r"\b(not|never)\b|n't", re.IGNORECASE)
PER_ITEM = re.compile(
    r"\bper[- ](?:item|file|instance)\b|\beach (?:item|file|instance)\b"
    r"|\b(?:\d+|n|many|several|multiple|parallel)\s+instances\b",
    re.IGNORECASE,
)
BATCH = re.compile(r"^(?:batch\s*)?0*(\d+)$", re.IGNORECASE)
Block = list[tuple[int, str]]


@dataclass(frozen=True)
class Row:
    line: int
    batch: str
    role: str
    writes: tuple[str, ...]
    label: str
    wanted: str
    note: str


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def word(cell: str) -> str:
    return cell.strip().strip("`").strip().lower()


def segments(path: str) -> list[str] | None:
    """Path segments, case-folded; None when the path is unknown (it then overlaps everything)."""
    p = unicodedata.normalize("NFC", path.strip().strip("`").strip()).replace("\\", "/").casefold()
    if p.startswith(("/", "~")) or "{" in p or UNKNOWN_PATH.search(p):
        return None
    parts = p.split("/")
    if ".." in parts:
        return None
    return [s for s in parts if s not in ("", ".")]


def touches(a: str, b: str) -> bool:
    """True when two paths or globs may name the same file."""
    sa, sb = segments(a), segments(b)
    if not sa or not sb:  # unknown, or the repository root
        return True
    for x, y in zip(sa, sb):
        if "**" in x or "**" in y:
            return True
        gx, gy = any(c in x for c in "*?["), any(c in y for c in "*?[")
        if gx and gy:
            continue  # two globs in one segment: assume they can match the same name
        if gx or gy:
            glob, name = (x, y) if gx else (y, x)
            if not fnmatchcase(name, glob):
                return False
        elif x != y:
            return False
    return True  # one is a directory prefix of the other


def overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    if not a or not b:  # an empty Writes cell means the paths are unknown
        return True
    return any(touches(x, y) for x in a for y in b)


def is_writers_heading(line: str) -> bool:
    """`## Writers`, also with a colon, bold, a number, `table` or a `(note)` around the word."""
    m = HEADING.match(line)
    if not m:
        return False
    title = m.group(1).replace("*", "").replace("_", "").strip().rstrip(":").strip().casefold()
    title = re.sub(r"^\d+[.)]?\s+", "", title)
    if title.endswith(")") and "(" in title:
        title = title[: title.index("(")].strip()
    return title.removesuffix(" table") == "writers"


def is_per_item(path: str) -> bool:
    return any(c in path for c in "*?[") or ("<" in path and ">" in path)


def is_separator(text: str) -> bool:
    return set(text.replace("|", "").strip()) <= set("-: ")


def scan(lines: list[str]) -> tuple[list[tuple[int, list[Block]]], list[tuple[int, str]]]:
    """Return, per Writers heading, its blocks of table lines (a blank line ends a block), and
    the unfenced lines."""
    found: list[tuple[int, list[Block]]] = []
    prose: list[tuple[int, str]] = []
    fence: str | None = None
    state = "none"  # none, wait (heading seen, no row yet), in (inside a block) or gap (blank)
    for n, line in enumerate(lines, 1):
        m = FENCE.match(line)
        if m:
            run = m.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
            state = "none"
            continue
        if fence is not None:
            continue
        prose.append((n, line))
        if is_writers_heading(line):
            found.append((n, []))
            state = "wait"
        elif state != "none" and line.lstrip().startswith("|"):
            if state != "in":
                found[-1][1].append([])
            found[-1][1][-1].append((n, line))
            state = "in"
        elif line.strip() and state != "none":
            if state != "wait" or ANY_HEADING.match(line):  # a sentence may precede the table
                state = "none"
        elif not line.strip() and state == "in":
            state = "gap"
    return found, prose


def tables_of(heading: int, blocks: list[Block], out: list[str], path: str) -> list[Block]:
    """A block with a separator row second starts a table; a header-less block after a blank line
    continues the previous table, and is reported."""
    result: list[Block] = []
    for block in blocks:
        if result and not (len(block) > 1 and is_separator(block[1][1])):
            out.append(f"{path}:{block[0][0]}: W7 blank line inside the Writers table")
            result[-1] = result[-1] + block
        else:
            result.append(block)
    if not result:
        out.append(f"{path}:{heading}: W7 Writers heading has no table under it")
    return result


def parse(raw: Block, out: list[str], path: str) -> list[Row]:
    def bad(n: int, rule: str, msg: str) -> None:
        out.append(f"{path}:{n}: {rule} {msg}")

    if len(raw) > MAX_ROWS + 2:
        bad(raw[0][0], "W10", f"table has {len(raw) - 2} rows, more than the {MAX_ROWS} allowed")
        return []
    body = [(n, cells(t)) for n, t in raw if not is_separator(t)]
    if len(body) < 2:
        bad(raw[0][0], "W7", "Writers table has no header and data row")
        return []
    head = [word(c) for c in body[0][1]]
    index: dict[str, int] = {}
    for col in COLUMNS:
        found = [i for i, h in enumerate(head) if h.startswith(col)]
        if not found:
            bad(body[0][0], "W7", f"missing column {col!r}")
        else:
            index[col] = found[0]
    if len(index) < len(COLUMNS):
        return []
    rows: list[Row] = []
    for n, cs in body[1:]:
        cs = cs + [""] * (len(head) - len(cs))
        cell = cs[index["writes"]]
        items = [p.strip().strip("`").strip() for p in cell.split(",")]
        writes = tuple(p for p in items if p)
        if len(cell) > MAX_CELL or len(writes) > MAX_PATHS:
            bad(n, "W10", f"Writes cell over {MAX_CELL} characters or {MAX_PATHS} paths")
            writes = ()
        batch = cs[index["batch"]].strip()
        m = BATCH.match(batch)
        if batch and not m:
            bad(n, "W7", f"Batch {batch!r} is not a whole number")
        rows.append(
            Row(
                n,
                str(int(m.group(1))) if m else batch,
                cs[index["role"]].strip(),
                writes,
                word(cs[index["label"]]),
                word(cs[index["wanted"]]),
                cs[index["mechanism"]].strip(),
            )
        )
        if not rows[-1].batch or not rows[-1].role:
            bad(n, "W7", "row has no Batch or no Role")
    return rows


def overclaims(text: str) -> bool:
    """A line that says advisory and uses an overclaim word with no not or never just before it."""
    if "advisory" not in text.lower():
        return False
    for m in OVERCLAIM.finditer(text):
        near = " ".join(text[max(0, m.start() - 200) : m.start()].split()[-NEGATION_WINDOW:])
        if not NEGATION.search(near):
            return True
    return False


def check_rows(rows: list[Row], out: list[str], path: str) -> None:
    def bad(r: Row, rule: str, msg: str) -> None:
        out.append(f"{path}:{r.line}: {rule} {r.role or '?'}: {msg}")

    for i, r in enumerate(rows):
        for what, value in (("Label", r.label), ("Wanted", r.wanted)):
            if value not in LABELS:
                bad(r, "W1", f"{what} {value!r} is not one of {', '.join(LABELS)}")
        if r.label in ("enforced", "workspace-enforced") and not r.note:
            bad(r, "W4", f"{r.label} needs the mechanism that makes it true")
        lowered = r.label in LABELS and r.wanted in LABELS
        if lowered and LABELS.index(r.label) > LABELS.index(r.wanted) and not r.note:
            bad(r, "W5", f"lowered from {r.wanted} to {r.label} with no reason")
        if PER_ITEM.search(r.role) and not (r.writes and all(map(is_per_item, r.writes))):
            bad(r, "W9", "role runs per item but a Writes path has no <item> part or glob")
        mates = [o for o in rows if o is not r and o.batch == r.batch]
        if r.label == "serialised" and mates:
            bad(r, "W3", f"serialised but batch {r.batch} also holds {mates[0].role}")
        for o in rows[i + 1 :]:
            both = {r.label, o.label} <= {"enforced", "advisory"}
            if o.batch == r.batch and both and overlap(r.writes, o.writes):
                bad(o, "W2", f"Writes overlap {r.role} in batch {r.batch}")


def check_file(path: Path, require: bool, out: list[str]) -> int:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    found, prose = scan(lines)
    name = path.as_posix()
    count = 0
    for heading, blocks in found:
        for table in tables_of(heading, blocks, out, name):
            count += 1
            check_rows(parse(table, out, name), out, name)
    if require and not found:
        out.append(f"{name}:1: W8 no Writers table")
    for n, text in prose:
        if overclaims(text):
            out.append(f"{name}:{n}: W6 advisory ownership described as exclusive: {text.strip()}")
    return count


def main(argv: list[str]) -> int:
    require = "--require" in argv[1:]
    files = [a for a in argv[1:] if a != "--require"]
    if not files or any(a.startswith("-") for a in files):
        print("usage: check_writers.py [--require] FILE.md [FILE.md ...]")
        return 2
    out: list[str] = []
    seen = 0
    for f in files:
        try:
            seen += check_file(Path(f), require, out)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"check_writers: cannot read {f}: {exc}")
            return 2
    print("\n".join(out + [f"check_writers: {len(out)} violation(s), {seen} Writers table(s)"]))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
