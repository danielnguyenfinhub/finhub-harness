#!/usr/bin/env python3
"""Package a generated harness so it can be installed outside the project that built it.

    package_harness.py CLAUDE_DIR --name NAME [--out DIR] [--description TEXT]
                       [--version X.Y.Z] [--install-user]

CLAUDE_DIR is the harness's `.claude` directory (`skills/*/SKILL.md`, optional `agents/*.md`).

Writes into DIR (default `dist`):
  NAME.plugin          plugin zip (`.claude-plugin/plugin.json`, `skills/`, `agents/`) for
                       Claude Cowork; unzipped, it is a Claude Code plugin directory
  <skill>-skill.zip    one per skill, the skill folder alone, for a Claude chat upload

--install-user also copies the skills and agents into `~/.claude/` (Claude Code, every project).
It never overwrites: if any target exists it copies nothing and exits 4.

Exit 0 built, 2 bad call or bad input, 4 refused install. Symlinks are never packed or copied.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

NAME_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
SKIP_DIRS = {".git", ".venv", "__pycache__"}


def _files(root: Path) -> list[Path]:
    """Regular files under root, sorted; no symlinks, caches, backups or workspaces."""
    out: list[Path] = []
    for d, dirs, names in os.walk(root):  # os.walk does not follow directory symlinks
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("_workspace"))
        for n in sorted(names):
            p = Path(d) / n
            if p.is_file() and not p.is_symlink() and not n.endswith(".pyc") and ".bak" not in n:
                out.append(p)
    return out


def _zip(out: Path, entries: list[tuple[Path, str]]) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in entries:
            z.write(src, arc)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Package a generated harness for Claude Code, Cowork and chat."
    )
    ap.add_argument("claude_dir", type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", type=Path, default=Path("dist"))
    ap.add_argument("--description", default="")
    ap.add_argument("--version", default="0.1.0")
    ap.add_argument("--install-user", action="store_true")
    a = ap.parse_args(argv)

    def bad(msg: str) -> int:
        print(f"ERROR: {msg}", file=sys.stderr)
        return 2

    if not NAME_RE.fullmatch(a.name) or len(a.name) > 64:
        return bad(f"--name must be kebab-case, at most 64 characters: {a.name!r}")
    desc = a.description or f"{a.name}: a harness built with finhub-harness."
    if not 1 <= len(desc) <= 500:
        return bad(f"--description is {len(desc)} characters; allowed 1-500")
    root = a.claude_dir
    skills = sorted(
        d
        for d in (root / "skills").glob("*")
        if d.is_dir()
        and not d.is_symlink()
        and (d / "SKILL.md").is_file()
        and NAME_RE.fullmatch(d.name)
    )
    if not skills:
        return bad(f"no skills/<kebab-case-name>/SKILL.md under {root}")
    agents_dir = root / "agents"
    agents = [p for p in _files(agents_dir) if p.suffix == ".md"] if agents_dir.is_dir() else []

    a.out.mkdir(parents=True, exist_ok=True)
    plugin = a.out / f"{a.name}.plugin"
    manifest = (
        json.dumps({"name": a.name, "version": a.version, "description": desc}, indent=2) + "\n"
    )
    with zipfile.ZipFile(plugin, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(".claude-plugin/plugin.json", manifest)
        for s in skills:
            files = _files(s)
            for f in files:
                z.write(f, f"skills/{s.name}/{f.relative_to(s).as_posix()}")
            _zip(
                a.out / f"{s.name}-skill.zip",
                [(f, f"{s.name}/{f.relative_to(s).as_posix()}") for f in files],
            )
            print(f"BUILT: {a.out / (s.name + '-skill.zip')}  (Claude chat: upload as a skill)")
        for f in agents:
            z.write(f, f"agents/{f.relative_to(agents_dir).as_posix()}")
    print(
        f"BUILT: {plugin}  (Claude Cowork: add in plugin settings; Claude Code: unzip, then claude --plugin-dir DIR)"
    )
    if agents:
        print(
            f"NOTE: installed as a plugin, agents are named {a.name}:<agent>; a skill that calls a bare"
        )
        print(
            "      agent name may not find it. For Claude Code, --install-user keeps the bare names."
        )

    if a.install_user:
        home = Path.home() / ".claude"
        plan = [(s, home / "skills" / s.name) for s in skills]
        plan += [(f, home / "agents" / f.relative_to(agents_dir)) for f in agents]
        taken = [str(dst) for _, dst in plan if dst.exists() or dst.is_symlink()]
        if taken:
            print(
                "REFUSED: already installed, nothing copied: " + ", ".join(taken), file=sys.stderr
            )
            return 4
        for src, dst in plan:
            for f in _files(src) if src.is_dir() else [src]:
                target = dst / f.relative_to(src) if src.is_dir() else dst
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
            print(f"INSTALLED: {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
