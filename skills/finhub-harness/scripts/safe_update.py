"""Plan an update of installed files against a stored baseline, and stage conflicts. It never edits a live file.

Usage, run from the project root:
  safe_update.py plan --baseline DIR --local DIR --upstream DIR
  safe_update.py stage --baseline DIR --local DIR --upstream DIR --out DIR
  safe_update.py markers FILE [FILE ...]
Exit 0 clean; 4 a conflict was found (plan, stage) or a conflict marker is left (markers); 2 usage error.

BASE is the copy installed last time, LOCAL is what is on disk now, UPSTREAM is the new version. For each
path in any of the three the decision is made from three comparisons, before any merge tool is called:
a file the user never edited takes upstream; a file upstream did not change, or edited to the same text,
keeps local; only when all three differ is a merge needed, and then nothing is merged here. A file a
person edited and upstream removed, a file removed locally that upstream changed, a path that exists on
disk but was never installed and differs from upstream, and a symlink are conflicts with a named reason.
`stage` copies BASE, LOCAL and UPSTREAM of each conflicting path under OUT and changes nothing else.
Rules R1-R6 are in skills/finhub-harness/references/safe-update.md.
Decision order and per-path cases adapted from references/repository_harness/crates/harness/src/application/service.rs:516
and :238; conflict reasons from references/repository_harness/crates/harness/src/domain/model.rs:155;
staging apart from live files from
references/repository_harness/docs/decisions/0025-latest-release-self-update-and-human-directed-conflicts.md:49;
marker lines from references/repository_harness/crates/harness/src/application/service.rs:560 (MIT, Hoang Nguyen),
ideas only.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

MARKERS = ("<<<<<<< ", "||||||| ", "=======", ">>>>>>> ")


def decide(base: bytes | None, local: bytes | None, up: bytes | None) -> tuple[str, str]:
    """(action, reason) for one path; None means the file is absent. Pure."""
    if base is None:
        if local is None:
            return ("create", "new upstream file") if up is not None else ("none", "absent")
        if up is None:
            return "preserve", "not installed, not upstream: the user's own file"
        if local == up:
            return "keep", "same text as upstream"
        return "conflict", "existing-unmanaged-path"
    if local is None:
        if up is None:
            return "none", "removed on both sides"
        if up == base:
            return "keep-local", "removed locally, upstream unchanged"
        return "conflict", "missing-managed-file"
    if up is None:
        if local == base:
            return "delete", "unedited locally, removed upstream"
        return "conflict", "modified-but-removed"
    if local == up:
        return "keep", "same text as upstream"
    if local == base:
        return "update", "unedited locally, upstream changed"
    if up == base:
        return "keep-local", "edited locally, upstream unchanged"
    return "conflict", "overlapping-changes"


def _files(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if not p.is_dir()}


def _read(p: Path | None) -> bytes | None:
    return None if p is None else p.read_bytes()


def plan(base: Path, local: Path, up: Path) -> list[tuple[str, str, str]]:
    trees = [_files(base), _files(local), _files(up)]
    out: list[tuple[str, str, str]] = []
    for rel in sorted({k for t in trees for k in t}):
        paths = [t.get(rel) for t in trees]
        if any(p is not None and p.is_symlink() for p in paths):
            out.append(("conflict", rel, "unsafe-path"))
            continue
        action, reason = decide(*(_read(p) for p in paths))
        if action != "none":
            out.append((action, rel, reason))
    return out


def _roots(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    roots = (Path(args.baseline), Path(args.local), Path(args.upstream))
    for r in roots:
        if not r.is_dir():
            raise SystemExit(f"REFUSED: {r} is not a directory")
    return roots


def _print(rows: list[tuple[str, str, str]]) -> int:
    for action, rel, reason in rows:
        print(f"PLAN {action} {rel} ({reason})")
    conflicts = sum(a == "conflict" for a, _, _ in rows)
    print(f"SUMMARY: {len(rows)} path(s), {conflicts} conflict(s)")
    return 4 if conflicts else 0


def stage(args: argparse.Namespace) -> int:
    base, local, up = _roots(args)
    out = Path(args.out).resolve()
    if out == local.resolve() or local.resolve() in out.parents:
        raise SystemExit(
            "REFUSED: --out must not be inside the local tree; it would change live files"
        )
    rows = plan(base, local, up)
    for action, rel, _ in rows:
        if action != "conflict":
            continue
        for label, root in (("BASE", base), ("LOCAL", local), ("UPSTREAM", up)):
            src = root / rel
            if src.is_file() and not src.is_symlink():
                dest = out / rel / label
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
    return _print(rows)


def markers(files: list[str]) -> int:
    bad = 0
    for name in files:
        for n, line in enumerate(Path(name).read_text("utf-8", errors="replace").splitlines(), 1):
            if line.startswith(MARKERS) or line == "=======":
                print(f"MARKER {name}:{n}")
                bad += 1
    print(f"SUMMARY: {bad} marker line(s)")
    return 4 if bad else 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="safe_update.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "stage"):
        p = sub.add_parser(name)
        for flag in ("--baseline", "--local", "--upstream"):
            p.add_argument(flag, required=True)
        if name == "stage":
            p.add_argument("--out", required=True)
    sub.add_parser("markers").add_argument("files", nargs="+")
    args = ap.parse_args(argv)
    if args.cmd == "markers":
        return markers(args.files)
    if args.cmd == "stage":
        return stage(args)
    return _print(plan(*_roots(args)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
