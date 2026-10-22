"""Check that each `references/<sub>/<path>:<line>` cite in a document exists at the pinned commit.

Usage, run from the project root (the repository that pins the submodules):
  cite_check.py DOC [DOC ...]

A cite is `references/<sub>/<path>:<a>` or `:<a>-<b>`, bare or in backticks, at the start of a
token. Continuations `, :<c>`, `; :<c>` and ` and :<c>` right after a cite reuse its path. When <sub>
is a submodule path in .gitmodules, the file is read from the tree of the gitlink in the index (the
pin); when `references/<sub>/<path>` is a file the project itself tracks, from its index entry.
Nothing is read from the working tree, nothing is fetched (every git call runs with
protocol.allow=never), and the document's path text is only looked up in a listing, never passed to
git or to a shell. Every token that starts with `references/` and holds a colon and a digit is
either checked, BAD or SKIPPED with a reason; none is dropped silently. Nothing is hashed.

Exit 0: every cite exists and its lines are in range. Exit 4: at least one BAD line. Exit 3: no
BAD line, but something could not be read (no .gitmodules, no index, no git, a submodule not
checked out, its pin or a cited blob not in the local object store), so the check is incomplete,
not passed. Exit 2: bad call or an unreadable DOC. Any other exit is a crash and is not a pass. In
range is not support: the judge still opens the line (quality-gates.md 1-4 and 2-1).

Reading the cited file from git at a recorded commit, and refusing a start below 1, an end before
the start and an end past the file, are adapted from
references/repository_harness/.agents/skills/audit-onboarding-proposal/scripts/validate_evidence_capsule.py:141-158
and references/repository_harness/.agents/skills/onboard-repository/scripts/emit_evidence_bundle.py:81-86
(MIT). The cite grammar, the pin lookup, the submodule states and the exit codes are new here.
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from pathlib import Path

USAGE = "usage: cite_check.py DOC [DOC ...]"
START = re.compile(r"(?<![\w./-])references/")
CITE = re.compile(r"(?<![\w./-])references/(?P<rel>[\w.][^\s`|<>\"',;:*]*):")
LINES = r"([0-9]+)(?:-([0-9]+))?(?![\w\-–—])"
FIRST = re.compile(LINES)
MORE = re.compile(r"`?(?:(?:,\s*|;\s*|,?\s+and\s+)`?:|,\s*)" + LINES)  # `, :c` or a list `, c`
DIGITS = 9  # a longer line number is BAD, never passed to int()
UNREAD = "unread"  # the source cannot be read, so the cite is neither checked nor BAD
SKIP = "SKIP: "  # problem() prefix for a cite that is reported SKIPPED, never checked
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}  # a hook's GIT_DIR
ENV.update(GIT_NO_LAZY_FETCH="1", GIT_TERMINAL_PROMPT="0")  # not every git honours the first
# A command-line -c outranks every config file; protocol.<name>.allow is read before
# protocol.allow, so each transport git knows is named too (a user's protocol.file.allow=always).
NO_FETCH: tuple[str, ...] = ("-c", "protocol.allow=never") + tuple(
    x
    for p in ("file", "git", "ssh", "http", "https", "ext")
    for x in ("-c", f"protocol.{p}.allow=never")
)
Tree = dict[str, tuple[str, str]]  # path -> (mode, object id)


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", *NO_FETCH, "-C", str(cwd), *args], capture_output=True, env=ENV, check=False
        )
    except OSError as exc:  # no git binary
        return subprocess.CompletedProcess(["git"], 127, b"", str(exc).encode())


def first_line(p: subprocess.CompletedProcess[bytes]) -> str:
    lines = p.stderr.decode("utf-8", "replace").strip().splitlines()
    return lines[0] if lines else f"git exit {p.returncode}"


def listing(raw: bytes, ls_files: bool) -> Tree:
    """`ls-files -s -z` or `ls-tree -r -z` output as path -> (mode, object id)."""
    tree: Tree = {}
    for item in raw.decode("utf-8", "replace").split("\0"):
        if "\t" in item:
            meta, name = item.split("\t", 1)
            fields = meta.split()
            tree[name] = (fields[0], fields[1] if ls_files else fields[2])
    return tree


class Pins:
    """Trees read once; `why` says why a source is unreadable, `fatal` why nothing is."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.fatal = ""
        out = git(
            root, "config", "-z", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"
        )
        if out.returncode not in (0, 1):  # 1: no path entries at all
            self.fatal = f"cannot read .gitmodules: {first_line(out)}"
        # -z: each record is `key NL value NUL`, so a name with a space cannot split the value
        paths = [r.split("\n", 1)[-1] for r in os.fsdecode(out.stdout).split("\0") if "\n" in r]
        self.subs = {p.removeprefix("references/") for p in paths if p.startswith("references/")}
        idx = git(root, "ls-files", "-s", "-z", "--", "references/")
        if idx.returncode != 0 and not self.fatal:
            self.fatal = f"cannot read the index: {first_line(idx)}"
        index = listing(idx.stdout, ls_files=True)
        self.gitlinks = {k: oid for k, (mode, oid) in index.items() if mode == "160000"}
        self.project = {k: v for k, v in index.items() if v[0] != "160000"}  # tracked files
        self.trees: dict[str, Tree] = {}
        self.why: dict[str, str] = {}
        self.notices: list[str] = []
        self.blobs: dict[str, bytes | None] = {}
        self.dirs: dict[int, set[str]] = {}  # id(listing) -> every directory prefix in it

    def is_dir(self, tree: Tree, path: str) -> bool:
        if id(tree) not in self.dirs:
            self.dirs[id(tree)] = {n[:i] for n in tree for i, c in enumerate(n) if c == "/"}
        return path in self.dirs[id(tree)]

    def tree(self, sub: str) -> Tree | None:
        if sub not in self.trees and sub not in self.why:
            got = self._read(sub)
            if isinstance(got, str):
                self.why[sub] = got
            else:
                self.trees[sub] = got
        return self.trees.get(sub)

    def _read(self, sub: str) -> Tree | str:
        d = self.root / "references" / sub
        pin = self.gitlinks.get(f"references/{sub}")
        if pin is None:
            return "no gitlink for it in the index"
        top = git(d, "rev-parse", "--show-toplevel") if d.is_dir() else None
        here = os.fsdecode(top.stdout).strip() if top and top.returncode == 0 else ""
        if not here or Path(here).resolve() != d.resolve():
            return f"not checked out (git submodule update --init references/{sub})"
        if git(d, "cat-file", "-e", f"{pin}^{{commit}}").returncode != 0:
            return f"pin {pin[:7]} is not in its local object store (shallow or other clone)"
        head = os.fsdecode(git(d, "rev-parse", "HEAD").stdout).strip()
        if head != pin:
            self.notices.append(
                f"NOTICE references/{sub}: checkout {head[:7]} differs from the pin {pin[:7]}; "
                "cites were checked at the pin"
            )
        ls = git(d, "ls-tree", "-r", "-z", "--full-tree", pin)
        if ls.returncode != 0:
            return f"cannot list the pin {pin[:7]}: {first_line(ls)}"
        return listing(ls.stdout, ls_files=False)

    def blob(self, where: Path, oid: str) -> bytes | None:
        if oid not in self.blobs:
            p = git(where, "cat-file", "blob", oid)
            self.blobs[oid] = p.stdout if p.returncode == 0 else None
        return self.blobs[oid]


def entry_problem(pins: Pins, key: str, tree: Tree, path: str, where: Path, b: int) -> str | None:
    """Check one path of a listing; `key` names the source in an UNREAD reason."""
    entry = tree.get(path)
    if entry is None:
        if pins.is_dir(tree, path):
            return "a directory, not a file"
        return "missing file at the pin"
    mode, oid = entry
    if mode == "120000":
        return "a symlink (cite the file it points to)"
    if mode == "160000":
        return "a nested submodule"
    data = pins.blob(where, oid)
    if data is None:
        pins.why.setdefault(
            key, f"blob {oid[:7]} of {path} is not in the local object store; nothing was fetched"
        )
        return UNREAD
    if b"\0" in data:
        return "binary file"
    n = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    if b > n:
        return f"line {b} past the end (file has {n} lines)"
    return None


def problem(pins: Pins, rel: str, sa: str, sb: str) -> str | None:
    """The reason a cite of references/<rel> is BAD, UNREAD when it cannot be read, else None."""
    parts = rel.split("/")
    sub, path = parts[0], "/".join(parts[1:])
    if any(p in ("", ".", "..") for p in parts) or "\\" in rel:
        return "path escapes the submodule or is not normalised"
    if len(sa) > DIGITS or len(sb) > DIGITS:
        return f"line number too large (more than {DIGITS} digits)"
    a, b = int(sa), int(sb)
    if a < 1:
        return "line 0 or less (lines start at 1)"
    if b < a:
        return f"range inverted ({a}-{b})"
    if sub in pins.subs and path:
        tree = pins.tree(sub)
        if tree is None:
            return UNREAD
        return entry_problem(pins, sub, tree, path, pins.root / "references" / sub, b)
    full = f"references/{rel}"
    if full in pins.project or pins.is_dir(pins.project, full):
        why = entry_problem(pins, "", pins.project, full, pins.root, b)
        return "missing file in the index" if why == "missing file at the pin" else why
    if not path:
        return (
            SKIP
            + "not a tracked file under references/; write a skill's file from the project root"
        )
    return "unknown submodule (neither a .gitmodules path nor a tracked file under references/)"


def check(pins: Pins, doc: str, text: str) -> tuple[list[str], dict[str, int]]:
    """(BAD and SKIPPED lines, counts) for one document."""
    out: list[str] = []
    count = {"checked": 0, "skipped": 0, "unread": 0}
    for no, line in enumerate(text.split("\n"), 1):
        starts = [s.start() for s in START.finditer(line)]
        after = {s: e for s, e in zip(starts, starts[1:] + [len(line)])}  # next candidate start
        read: set[int] = set()
        for m in CITE.finditer(line):
            read.add(m.start())
            first = FIRST.match(line, m.end())
            shown = line[m.start() : after[m.start()]].split()[0]  # bounded: linear
            prose = not re.search(r"[./]", m["rel"]) and not re.search(r":[0-9]", shown)
            if first is None and prose:
                continue  # `references/openrig: ...` is prose, not a cite
            if first is None:
                count["skipped"] += 1
                out.append(f"SKIPPED {doc}:{no}: {shown}: no line number after the colon")
                continue
            spans = [first.groups()]
            pos = first.end()
            while (more := MORE.match(line, pos)) is not None:
                spans.append(more.groups())
                pos = more.end()
            for sa, sb in spans:
                why = problem(pins, m["rel"], sa, sb or sa)
                if why == UNREAD:
                    count["unread"] += 1
                    continue
                if why and why.startswith(SKIP):
                    count["skipped"] += 1
                    out.append(f"SKIPPED {doc}:{no}: references/{m['rel']}:{sa}: {why[len(SKIP):]}")
                    continue
                count["checked"] += 1
                if why:
                    cite = f"references/{m['rel']}:{sa}" + (f"-{sb}" if sb else "")
                    out.append(f"BAD {doc}:{no}: {cite}: {why}")
        for s in starts:
            if s in read:
                continue
            token = line[s : after[s]].split()[0]
            if re.search(r":[0-9]", token):
                count["skipped"] += 1
                out.append(
                    f"SKIPPED {doc}:{no}: {token}: not read as a cite "
                    "(a character the grammar does not read comes before the colon)"
                )
    return out, count


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):  # a non-UTF-8 path name must print, not raise
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="backslashreplace")
    if not argv or any(a.startswith("-") for a in argv):
        print(USAGE, file=sys.stderr)
        return 2
    root = Path.cwd()
    if not (root / ".gitmodules").is_file():
        print("UNAVAILABLE: no .gitmodules in the current directory, so no pin can be read")
        return 3
    texts: list[tuple[str, str]] = []
    for doc in argv:
        try:
            texts.append((doc, Path(doc).read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {doc}: {exc}", file=sys.stderr)
            return 2
    pins = Pins(root)
    if pins.fatal:
        print(f"UNAVAILABLE: {pins.fatal}")
        return 3
    lines: list[str] = []
    total = {"checked": 0, "skipped": 0, "unread": 0}
    for doc, text in texts:
        out, count = check(pins, doc, text)
        lines += out
        for k in total:
            total[k] += count[k]
    for line in lines + pins.notices:
        print(line)
    for sub, why in sorted(pins.why.items()):
        print(f"UNAVAILABLE {'references/' + sub if sub else 'project index'}: {why}")
    bad = sum(line.startswith("BAD ") for line in lines)
    print(
        f"SUMMARY: checked {total['checked']}, bad {bad}, skipped {total['skipped']}, "
        f"unavailable {total['unread']}"
    )
    if bad:
        return 4
    return 3 if pins.why else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
