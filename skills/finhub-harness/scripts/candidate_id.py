"""Name the exact tree a QA or judge verdict covers, and say whether it still does.

Usage:
  candidate_id.py id [--root DIR] [--paths P [P ...]] [--exclude P ...] [--max-bytes N]
  candidate_id.py check RECORD [--root DIR] [--tree-only] [--max-bytes N]
RECORD is a verdict file (its `CANDIDATE:` line must be among the first 8 lines) or a `CANDIDATE:`
line itself. Exit 0 ok (the id is printed, or the tree is the one recorded); 3 stop (the verdict is
stale, unbound, unverified, or the tree cannot be fully hashed or moved while it was hashed); 2 bad
usage or an unreadable input. The same 0/2/3 meaning as state_ledger.py. Rules C1-C8 are in
skills/finhub-harness/references/quality-gates.md section 3-7.

Two kinds. `git:<head12>+<tree16>` covers a git worktree: the commit, plus the bytes, executable bit
and symlink text of every tracked file and every untracked file that .gitignore does not hide, plus
the pinned commit of each submodule. `files:<tree16>` covers the named paths only (a patch file, a
design document, a directory) and is the only kind on a tree with no git. Not covered, ever: ignored
files, the contents of a submodule, what a symlink points at, file times, and anything the judge
did not open. The digest is for noticing an accidental change, not for tamper evidence.

Binding a verdict to one exact commit and refusing a mismatch is adapted from
references/openrig/scripts/gate-lane.mjs:48-49 and scripts/gate-lane-consume.mjs:23-25 (Apache-2.0).
Rewritten, not copied; no daemon, no network.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from urllib.parse import quote, unquote

MAX_BYTES = 256 * 1024 * 1024  # a larger file is listed as uncovered, never read
DEFAULT_EXCLUDES = ("_workspace/",)  # the team's notes and verdict files must not move their own id
HEAD_LEN, DIGEST_LEN = 12, 16
TOKEN = re.compile(r"^(?:git:(?:[0-9a-f]{12}|unborn)\+[0-9a-f]{16}|files:[0-9a-f]{16}|unverified)$")
LINE = re.compile(r"^\s*CANDIDATE:\s*(\S.*?)\s*$")
OPEN_MARK = "could not open directory"
OPEN_WARNING = re.compile(r"warning: " + OPEN_MARK + r" '(.*?)': [^\n]*(?:\n|$)", re.DOTALL)
UNPLACED = "(git could not open a directory)"
Entry = tuple[bytes, str, bytes]  # path, kind (f x l g m u), payload


class Usage(Exception):
    """Bad arguments or an input that cannot be read: exit 2."""


@dataclass
class Result:
    kind: str  # git | files
    digest: str
    n: int
    head: str = ""
    excludes: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    unstable: str = ""

    @property
    def token(self) -> str:
        return f"git:{self.head}+{self.digest}" if self.kind == "git" else f"files:{self.digest}"

    @property
    def line(self) -> str:
        out = f"{self.token} n={self.n} excludes={_enc(self.excludes)}"
        out += f" paths={_enc(self.paths)}" if self.kind == "files" else ""
        return out + (f" partial={len(self.skipped)}" if self.skipped else "")


def _enc(items: list[str]) -> str:
    return ",".join(quote(i, safe="/_.-~") for i in items) or "-"


def _dec(text: str) -> list[str]:
    return [] if text in ("", "-") else [unquote(i) for i in text.split(",")]


def _clean_rel(p: str) -> str:
    q = os.path.normpath(p).replace(os.sep, "/")
    if not p or os.path.isabs(p) or q == ".." or q.startswith("../") or "\x00" in p:
        raise Usage(f"path must be relative and inside the root: {p!r}")
    return "" if q == "." else q


def _excluded(rel: str, excl: list[str]) -> bool:
    return any(rel == e.rstrip("/") or rel.startswith(e.rstrip("/") + "/") for e in excl)


def _git_raw(top: str, *args: str) -> tuple[bytes, bytes]:
    """(stdout, stderr) of a git call that exited 0; any other exit is a Usage error."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["LC_ALL"] = "C"
    try:
        r = subprocess.run(
            ["git", "-C", top, "-c", "core.quotepath=off", *args],
            capture_output=True,
            env=env,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Usage(f"git could not run: {e}") from e
    if r.returncode != 0:
        raise Usage(f"git {args[0]} failed: {r.stderr.decode('utf-8', 'replace').strip()[:200]}")
    return r.stdout, r.stderr


def _git(top: str, *args: str) -> bytes:
    return _git_raw(top, *args)[0]


def _sha_file(path: str, st: os.stat_result, cap: int) -> tuple[str, str]:
    """(hex, '') or ('', reason). The file is opened without following a symlink and read in
    chunks; a file whose size or time moved while it was read is reported as unstable."""
    if st.st_size > cap:
        return "", f"over the {cap}-byte limit ({st.st_size} bytes)"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as e:
        return "", f"unreadable: {e.strerror or e.errno}"
    h, got = hashlib.sha256(), 0
    try:
        with os.fdopen(fd, "rb") as f:
            s2 = os.fstat(f.fileno())
            if not stat.S_ISREG(s2.st_mode) or s2.st_ino != st.st_ino:
                return "", "unstable: replaced while hashing"
            while chunk := f.read(1 << 20):
                got += len(chunk)
                if got > cap:
                    return "", f"over the {cap}-byte limit (grew while hashing)"
                h.update(chunk)
            s3 = os.fstat(f.fileno())
    except OSError as e:
        return "", f"unreadable: {e.strerror or e.errno}"
    if got != s2.st_size or (s3.st_size, s3.st_mtime_ns) != (s2.st_size, s2.st_mtime_ns):
        return "", "unstable: changed while hashing"
    return h.hexdigest(), ""


def _sig(path: str) -> tuple[int, int, int, int] | None:
    """What a file looked like when it was last touched; None when it is not there."""
    try:
        st = os.lstat(path)
    except OSError:
        return None
    return st.st_mode, st.st_size, st.st_mtime_ns, st.st_ino


def _entry(
    top: str, real_top: str, rel: str, idx: tuple[str, str] | None, cap: int
) -> tuple[Entry, str]:
    """One tree entry and, when it cannot be covered, the reason (the entry then has kind u)."""
    pb = os.fsencode(rel)
    if idx and idx[0] == "!":  # a marker from _list_git, not a path of the tree
        return (pb, "u", b""), idx[1]
    parent = rel.rpartition("/")[0]
    full = os.path.join(top, rel)
    try:  # a symlinked directory on the way would make lstat read outside the tree
        if os.path.realpath(os.path.join(top, parent)) != os.path.join(real_top, parent).rstrip(
            "/"
        ):
            return (pb, "u", b""), "a directory on the path is a symlink"
        st = os.lstat(full)
    except FileNotFoundError:
        return (pb, "m", b""), ""
    except OSError as e:
        return (pb, "u", b""), f"unreadable: {e.strerror or e.errno}"
    if stat.S_ISLNK(st.st_mode):
        try:
            return (pb, "l", os.fsencode(os.readlink(full))), ""
        except OSError as e:
            return (pb, "u", b""), f"unreadable: {e.strerror or e.errno}"
    if stat.S_ISDIR(st.st_mode):
        if idx and idx[0] == "160000":
            return (pb, "g", idx[1].encode()), ""  # a submodule: its pin, not its files
        return (pb, "u", b""), "a directory (a nested repository or a replaced file)"
    if not stat.S_ISREG(st.st_mode):
        return (pb, "u", b""), "not a regular file"
    digest, why = _sha_file(full, st, cap)
    if why:
        return (pb, "u", b""), why
    return (pb, "x" if st.st_mode & 0o111 else "f", digest.encode()), ""


def _list_git(top: str) -> list[tuple[str, tuple[str, str] | None]]:
    cached: dict[str, tuple[str, str] | None] = {}
    for rec in _git(top, "ls-files", "-s", "-z").split(b"\0"):
        if not rec:
            continue
        meta, _, path = rec.partition(b"\t")
        mode, sha, stage = meta.decode().split(" ")
        p = os.fsdecode(path)
        if stage == "0":
            cached[p] = (mode, sha)
        else:  # an unmerged path is listed once and hashed from the worktree
            cached.setdefault(p, None)
    out = sorted(cached.items())
    others, warn = _git_raw(
        top, "-c", "core.excludesFile=/dev/null", "ls-files", "-o", "--exclude-standard", "-z"
    )
    names = {os.fsdecode(p) for p in others.split(b"\0") if p}
    # exit 0 yet a directory was not read: git says so on stderr, which is text, not NUL separated.
    # A name may hold a newline, so the whole text is searched, and every warning must be matched
    # to a path that exists, or the listing carries an entry that makes the id partial.
    # ponytail: a name holding `': ` is cut at its first `': `, so the SKIPPED line may show the
    # prefix instead of the full name; the exit code is still 3, because a prefix counts as placed
    # only when it is a directory of the tree (any directory there is reported as uncovered) and a
    # count mismatch adds a marker entry. Exact names for such a crafted tree: parse `-z` output.
    text, placed = os.fsdecode(warn), 0
    for m in OPEN_WARNING.finditer(text):
        name = m[1].rstrip("/")
        full = os.path.join(top, name)
        if name and os.path.isdir(full) and not os.path.islink(full):
            names.add(name)  # listed as a directory, so _entry reports it as uncovered
            placed += 1
    out += [(p, None) for p in sorted(names)]
    if text.count(OPEN_MARK) != placed:
        out.append((UNPLACED, ("!", "git could not open a directory and its name was not placed")))
    return out


def _digest(kind: str, excl: list[str], entries: list[Entry]) -> str:
    h = hashlib.sha256(b"candidate-v1\0" + kind.encode() + b"\0")
    for e in sorted(excl):
        h.update(b"x%d:%s" % (len(e.encode()), e.encode()))
    for path, k, payload in sorted(entries):
        h.update(b"%d:%s%s%d:%s" % (len(path), path, k.encode(), len(payload), payload))
    return h.hexdigest()[:DIGEST_LEN]


def _walk(
    root: str, paths: list[str], excl: list[str], missing_ok: bool, skipped: list[tuple[str, str]]
) -> list[str]:
    out: set[str] = set()
    for p in paths:
        rel = _clean_rel(p)
        try:
            st = os.lstat(os.path.join(root, rel))
        except OSError:
            if not missing_ok:
                raise Usage(f"no such path: {p}") from None
            out.add(rel)
            continue
        if not stat.S_ISDIR(st.st_mode):
            out.add(rel)
            continue
        walker = os.walk(
            os.path.join(root, rel),
            followlinks=False,
            onerror=lambda e: skipped.append(
                (str(e.filename), f"unreadable directory: {e.strerror}")
            ),
        )
        for dirpath, dirnames, filenames in walker:
            here = os.path.relpath(dirpath, root).replace(os.sep, "/")
            dirnames.sort()
            for (
                d
            ) in dirnames:  # a symlinked directory is one entry; followlinks=False never enters it
                if os.path.islink(os.path.join(dirpath, d)):
                    out.add(os.path.normpath(os.path.join(here, d)).replace(os.sep, "/"))
            out.update(
                os.path.normpath(os.path.join(here, f)).replace(os.sep, "/") for f in filenames
            )
    return sorted(r for r in out if not _excluded(r, excl))


def compute(
    root: str,
    paths: list[str] | None = None,
    excludes: list[str] | None = None,
    cap: int = MAX_BYTES,
    missing_ok: bool = False,
) -> Result:
    """Hash the candidate. With `paths` the kind is files; otherwise root must be a git worktree top."""
    if not os.path.isdir(root):
        raise Usage(f"root is not a directory: {root}")
    real_root = os.path.realpath(root)
    skipped: list[tuple[str, str]] = []
    if paths:
        excl = [e for e in (excludes or []) if e]
        kind, head = "files", ""
        pairs: list[tuple[str, tuple[str, str] | None]] = [
            (r, None) for r in _walk(real_root, paths, excl, missing_ok, skipped)
        ]
    else:
        top = _git(real_root, "rev-parse", "--show-toplevel").decode().strip()
        if os.path.realpath(top) != real_root:
            raise Usage(f"root is inside the repository at {top}; pass that directory")
        excl = [e for e in (DEFAULT_EXCLUDES if excludes is None else excludes) if e]
        kind = "git"
        head = _head(real_root)
        pairs = [(p, i) for p, i in _list_git(real_root) if not _excluded(p, excl)]
    entries: list[Entry] = []
    sigs: list[tuple[int, int, int, int] | None] = []
    for rel, idx in pairs:
        sigs.append(_sig(os.path.join(real_root, rel)))
        e, why = _entry(real_root, real_root, rel, idx, cap)
        entries.append(e)
        if why:
            skipped.append((rel, why))
    moved = any(_sig(os.path.join(real_root, rel)) != sg for (rel, _), sg in zip(pairs, sigs))
    again = (
        [(p, i) for p, i in _list_git(real_root) if not _excluded(p, excl)]
        if kind == "git"
        else [(r, None) for r in _walk(real_root, paths or [], excl, missing_ok, [])]
    )
    # a run that moves under its own id is refused, adapted from references/openrig/scripts/gate-lane.mjs:152 (Apache-2.0)
    r = Result(
        kind, _digest(kind, excl, entries), len(entries), head, excl, list(paths or []), skipped
    )
    if moved or again != pairs or (kind == "git" and _head(real_root) != head):
        r.unstable = "the tree changed while it was being hashed"
    return r


def _head(top: str) -> str:
    # adapted from references/openrig/scripts/gate-lane.mjs:48 (Apache-2.0)
    try:
        return _git(top, "rev-parse", "--verify", "-q", "HEAD").decode().strip()[:HEAD_LEN]
    except Usage:
        return "unborn"  # no commit yet; a repository that git itself rejects failed earlier


def read_record(arg: str) -> tuple[str, dict[str, str]] | None:
    """(token, fields) from a verdict file or a CANDIDATE line; None when the file has no such line."""
    if arg.lstrip().startswith("CANDIDATE:"):
        lines = [arg]
    else:
        try:
            with open(arg, "rb") as f:
                lines = f.read(65536).decode("utf-8-sig", "replace").splitlines()[:8]
        except OSError as e:
            raise Usage(f"cannot read {arg}: {e.strerror}") from e
    for ln in lines:
        m = LINE.match(ln)
        if m:
            parts = m.group(1).split()
            fields = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
            return parts[0], fields
    return None


def check(arg: str, root: str, tree_only: bool, cap: int) -> int:
    # a mismatch is refused, adapted from references/openrig/scripts/gate-lane-consume.mjs:23 (Apache-2.0)
    rec = read_record(arg)
    if rec is None:
        print("STATE: STALE\nREASON: unbound, the file has no CANDIDATE line in its first 8 lines")
        return 3
    token, f = rec
    if not TOKEN.match(token) or token == "unverified":
        why = "the id was recorded as unverified" if token == "unverified" else "malformed id"
        print(f"STATE: STALE\nREASON: {why}\nRECORDED: {token}")
        return 3
    excl, kind = _dec(f.get("excludes", "-")), token.split(":")[0]
    paths = _dec(f.get("paths", "-"))
    if kind == "files" and not paths:
        print(f"STATE: STALE\nREASON: a files id needs its paths= field\nRECORDED: {token}")
        return 3
    r = compute(root, paths if kind == "files" else None, excl, cap, missing_ok=True)
    now = r.token
    if r.unstable or r.skipped or r.n == 0:
        why = (
            r.unstable
            or ("uncovered: " + "; ".join(f"{p} ({w})" for p, w in r.skipped[:5]))
            or "empty candidate"
        )
        print(
            f"STATE: STALE\nREASON: the tree cannot be shown to match: {why}\nRECORDED: {token}\nNOW: {now}"
            f"\nEXCLUDES: {_enc(excl)}"
        )
        return 3
    same = token.split("+")[-1] == now.split("+")[-1] if tree_only else token == now
    if same:
        print(f"STATE: current\nRECORDED: {token}\nNOW: {now}\nEXCLUDES: {_enc(excl)}")
        return 0
    moved = kind == "git" and token.split("+")[0] != now.split("+")[0]
    changed = token.split("+")[-1] != now.split("+")[-1]
    why = " and ".join(["the commit moved"] * moved + ["the files differ"] * changed)
    print(f"STATE: STALE\nREASON: {why}\nRECORDED: {token}\nNOW: {now}\nEXCLUDES: {_enc(excl)}")
    return 3


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("id", "check"):
        p = sub.add_parser(cmd)
        p.add_argument("--root", default=".")
        p.add_argument("--max-bytes", type=int, default=MAX_BYTES)
        if cmd == "id":
            p.add_argument("--paths", nargs="+")
            p.add_argument("--exclude", action="append", default=[])
        else:
            p.add_argument("record")
            p.add_argument("--tree-only", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        if a.cmd == "check":
            return check(a.record, a.root, a.tree_only, a.max_bytes)
        excl = ([] if a.paths else list(DEFAULT_EXCLUDES)) + [_clean_rel(e) for e in a.exclude]
        r = compute(a.root, a.paths, excl, a.max_bytes)
    except Usage as e:
        print(f"candidate_id: {e}")
        return 2
    print(f"CANDIDATE: {r.line}")
    print(
        "COVERS: "
        + ("the commit; " if r.kind == "git" else "")
        + "bytes, executable bit and symlink text of the listed files"
    )
    print(
        "NOT-COVERED: ignored files, submodule contents, symlink targets, file times; digest is not tamper evidence"
    )
    for name, why in r.skipped[:10]:
        print(f"SKIPPED: {name} ({why})")
    if r.unstable or r.skipped or r.n == 0:
        print("REASON: " + (r.unstable or ("uncovered files" if r.skipped else "empty candidate")))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
