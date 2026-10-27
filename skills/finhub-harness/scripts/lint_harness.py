"""Lint a harness dir (agents/*.md, skills/*/SKILL.md). Exit 0 clean, 1 errors, 2 usage.
Adapted from references/crewai/lib/crewai/src/crewai/skills/validation.py:43 (MIT) and
references/deepseek_harness/packages/skill/skill/src/index.ts:20 (MIT);
link, bundled-file and duplicate-name rules adapted from references/meta_harness/scripts/validate_skills.py:72
and references/meta_harness/scripts/audit_harness.py:117 (Apache-2.0);
provenance rules (verified-*) adapted from references/openrig/packages/daemon/src/domain/skill-audit.ts:98-136
and references/openrig/packages/cli/src/lib/scope/trust.ts:33-48 (Apache-2.0);
pointer rules (pointer-marker, pointer-budget) adapted from
references/repository_harness/scripts/install-harness.sh:330-344 and
references/repository_harness/tests/installer/assert-agent-authority-contract.sh:35
(MIT, Hoang Nguyen)."""

from __future__ import annotations

import os
import re
import stat
import sys
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KEY_RE = re.compile(r"^([A-Za-z][\w-]*):\s?(.*)$")
REF_RE = re.compile(r"""(?:subagent_type|agentType)["']?\s*:\s*["']([A-Za-z0-9_-]+)["']""")
V1_RE = re.compile(r"TeamCreate\(|TeamDelete\(|team_name:|CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=")
SPAWN_RE = re.compile(r"\b(?:subagent_type|agentType|SendMessage)\b|\b(?:agent|Agent|Task)\(")
LAZY_RE = re.compile(
    r"\b(?:based\s+on\s+(?:your|the)\s+(?:findings|research)|as\s+(?:we\s+)?discussed)\b",
    re.IGNORECASE,
)
CONN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SECTION_RE = re.compile(r"^## Required connectors[ \t]*\n(.*?)(?=^#|\Z)", re.MULTILINE | re.DOTALL)
TABLE_RE = re.compile(r"^ *\| *Agent *\| *Required connector *\| *\n((?: *\|.*\n?)*)", re.MULTILINE)
ROW_RE = re.compile(r"^\|\s*`?([^|`]+?)`?\s*\|\s*`?([^|`]+?)`?\s*\|\s*$")
BUILTIN = {"general-purpose", "Explore", "Plan", "statusline-setup", "claude-code-guide"}
SKILL_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "version"}
SKILL_KEYS |= {"author", "tags", "disable-model-invocation", "user-invocable", "argument-hint"}
VERIFY_KEYS = {"last_verified", "verified_source", "review_days"}
SKILL_KEYS |= VERIFY_KEYS
DAY_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
WINDOW_RE = re.compile(r"[0-9]{1,4}")
LOCATOR_RE = re.compile(r"https?://\S+|\b(?:19|20)[0-9]{2}\b")
MAX_WINDOW = 3650
AGENT_KEYS = {"name", "description", "tools", "model", "color"}
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
LINK_RE = re.compile(r"!?\[[^\]\n]{0,300}\]\(\s*(<[^>\n]+>|[^)\s]+)")
# a definition: not a ^footnote, a path-like target, then end of line or a quoted/parenthesised title
DEF_RE = re.compile(
    r"^ {0,3}\[(?!\^)[^\]\n]{1,300}\]:\s*(<[^>\n]+>|(?=\S*(?:/|\.\w))[^\s<]\S*)\s*(?:[\"'(].*)?$"
)
CODE_RE = re.compile(r"`[^`\n]*`")
NONLOCAL_RE = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9+.-]*:|[/#{$~])"
)  # scheme, anchor, absolute, template
BUNDLED_RE = re.compile(
    r"(?<![\w./-])references/([A-Za-z0-9_][A-Za-z0-9_.-]*\.[A-Za-z0-9]+)(?![\w/-])"
)

POINTER_RE = re.compile(rb"<!-- finhub-harness:(begin|end) ([a-z0-9]+(?:-[a-z0-9]+)*) -->")
POINTER_BUDGET = 1600  # bytes of the block, both marker lines included

out: list[str] = []


def report(level: str, path: Path, rule: str, msg: str) -> None:
    out.append(f"{level} {path}: {rule} {msg}")


def read(path: Path) -> str:
    text = (raw := path.read_bytes()).decode("utf-8", errors="replace")
    if text.encode() != raw:
        report("ERROR", path, "encoding", "not valid UTF-8 (undecodable bytes replaced)")
    return text


def frontmatter(path: Path, text: str) -> dict[str, str] | None:
    """Parse the leading --- block into raw string values; None (and an error) if unusable."""
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        report("ERROR", path, "frontmatter", "missing --- delimited frontmatter")
        return None
    data: dict[str, str] = {}
    key = ""
    for line in lines[1 : lines.index("---", 1)]:
        m = KEY_RE.match(line)
        if m:
            key = m.group(1)
            data[key] = m.group(2).strip()
        elif key and (line.startswith((" ", "\t", "- ")) or not line.strip()):
            data[key] = (data[key] + " " + line.strip()).strip()
        elif not line.lstrip().startswith("#"):
            report("ERROR", path, "frontmatter", f"unparseable line: {line[:60]!r}")
            return None
    return data


def scalar(raw: str) -> str:
    """Value of a YAML scalar as written: quoted body, or unquoted text minus a # comment."""
    if raw[:1] in ('"', "'") and raw[1:].find(raw[0]) >= 0:
        return raw[1 : 1 + raw[1:].find(raw[0])]
    raw = re.sub(r"^[>|][-+]?\s*", "", raw)
    return raw.split(" #", 1)[0].strip()


def check_meta(path: Path, data: dict[str, str], known: set[str], expect: str | None) -> str:
    name, desc = scalar(data.get("name", "")), scalar(data.get("description", ""))
    if not name:
        report("ERROR", path, "name", "frontmatter name is missing or empty")
    elif len(name) > 64 or not NAME_RE.match(name):
        report("ERROR", path, "name", f"{name!r}: kebab-case, max 64 chars (got {len(name)})")
    if expect is not None and name and name != expect:
        report("ERROR", path, "dir-name", f"directory {expect!r} does not match name {name!r}")
    if not desc:
        report("ERROR", path, "description", "frontmatter description is missing or empty")
    elif len(desc) > 1024:
        report("WARN", path, "description", f"{len(desc)} chars; over the 1024-char skill limit")
    for k in sorted(set(data) - known):
        report("WARN", path, "unknown-key", f"frontmatter key {k!r} is not recognised")
    return name


def prose(text: str) -> Iterator[tuple[int, str]]:
    """(line number, line) outside ``` and ~~~ fences; an unclosed fence hides the rest."""
    fence = ""
    for n, line in enumerate(text.splitlines(), 1):
        m = FENCE_RE.match(line)
        if fence:
            # a closing fence uses the same character, is at least as long and has no info string
            if (
                m
                and m.group(1)[0] == fence[0]
                and len(m.group(1)) >= len(fence)
                and not line.strip(" \t`~")
            ):
                fence = ""
        elif m:
            fence = m.group(1)
        else:
            yield n, line


def check_links(path: Path, text: str) -> None:
    """Local markdown link targets must exist, resolved against the linking file's own directory."""
    for n, line in prose(text):
        found = (
            [m.group(1)] if (m := DEF_RE.match(line)) else LINK_RE.findall(CODE_RE.sub("", line))
        )
        for target in found:
            clean = unquote(target.strip("<>").split("#", 1)[0].split("?", 1)[0])
            if not clean or NONLOCAL_RE.match(clean):
                continue
            try:
                missing = not (path.parent / clean).exists()
            except (OSError, ValueError):  # over-long or NUL target: not a file we can judge
                continue
            if missing:
                report("ERROR", path, "broken-link", f"line {n}: {target!r} does not exist")


def check_bundled(path: Path, root: Path, text: str) -> None:
    """A top-level `references/<file>.<ext>` mention must exist in the skill dir or an ancestor dir
    up to the lint root's parent (repo-level files such as references/LICENSES.md resolve there).
    Deeper paths (references/<repo>/...) are submodule citations and are not checked."""
    stop = root.resolve().parent
    for n, line in prose(text):
        for ref in BUNDLED_RE.findall(line):
            d = path.resolve().parent
            while True:
                try:
                    found = (d / "references" / ref).exists()
                except OSError:  # over-long name: no such file can exist, so it is missing
                    found = False
                if found:
                    break
                if d in (stop, d.parent):
                    report(
                        "ERROR",
                        path,
                        "bundled-ref",
                        f"line {n}: references/{ref} does not exist "
                        "(create it, or cite it as <skill>/references/x.md or inside a code fence)",
                    )
                    break
                d = d.parent


def connectors(path: Path, body: str) -> set[str]:
    """Servers under '## Required connectors' (one per line, bullet and backticks optional)."""
    m = SECTION_RE.search(body)
    found: set[str] = set()
    for line in m.group(1).splitlines() if m else []:
        s = re.sub(r"^[-*]\s+", "", line.strip()).strip("`")
        if s and CONN_RE.match(s) and "__" not in s:
            found.add(s)
        elif s:
            report("ERROR", path, "connector", f"{s[:60]!r}: not a bare server name")
    return found


def preflight_rows(body: str) -> set[tuple[str, str]]:
    """(agent, server) rows of '| Agent | Required connector |' tables; skip {..}, none, separator."""
    lines = [ln.strip() for table in TABLE_RE.findall(body) for ln in table.splitlines()]
    found = [m.group(1, 2) for m in map(ROW_RE.match, lines) if m and "{" not in m.group(0)]
    return {(a.strip(), s.strip()) for a, s in found if a.strip("-: ").lower() not in ("", "none")}


def parse_day(raw: str) -> date | None:
    """A real calendar day written YYYY-MM-DD, else None (month 13 and 30 February are not days)."""
    if not DAY_RE.fullmatch(raw):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def check_provenance(path: Path, data: dict[str, str], today: date) -> None:
    """Opt-in: silent unless the skill sets a verified key. WARN only; every message ends with a fix."""
    present = sorted(VERIFY_KEYS & data.keys())
    if not present:
        return
    raw = scalar(data.get("last_verified", ""))
    if not raw:
        keys = ", ".join(present)
        msg = f"{keys} set but last_verified is missing or empty; fix: set last_verified to a YYYY-MM-DD day, or remove all three keys"
        report("WARN", path, "verified-orphan", msg)
        return
    day = parse_day(raw)
    if day is None:
        msg = f"last_verified {raw[:40]!r} is not a real YYYY-MM-DD date; fix: write the day as YYYY-MM-DD"
        report("WARN", path, "verified-date", msg)
        return
    if day > today:
        msg = (
            f"last_verified {raw} is after today ({today}); fix: set the day you re-read the source"
        )
        report("WARN", path, "verified-future", msg)
        return
    source = scalar(data.get("verified_source", ""))
    if not source or "skill.md" in source.lower() or not LOCATOR_RE.search(source):
        msg = "verified_source must name a document other than this skill, with a URL or a year; fix: name the document you re-read"
        report("WARN", path, "verified-bare", msg)
    window = scalar(data.get("review_days", ""))
    if not WINDOW_RE.fullmatch(window) or not 1 <= int(window) <= MAX_WINDOW:
        msg = f"review_days {window[:20]!r} is not valid and there is no default; fix: set whole days from 1 to {MAX_WINDOW}"
        report("WARN", path, "verified-window", msg)
        return
    if (age := (today - day).days) > int(window):
        msg = f"last verified {age} days ago; review_days is {window}; fix: re-read the source, then update last_verified"
        report("WARN", path, "verified-stale", msg)


def check_pointer(path: Path) -> None:
    """The finhub-harness block of CLAUDE.md: per orchestrator name one begin marker line above one
    end marker line, no other block's marker between them (ERROR), at most POINTER_BUDGET bytes (WARN).
    A marker is a whole line (trailing blanks allowed); silent when the file is absent or has none.
    The bytes outside every block (the change history among them) are never read for the budget."""
    try:  # stat and read in one try: is_file() raises on 3.11-3.13 and hides errors on 3.14
        if not stat.S_ISREG(path.stat().st_mode):
            return  # a directory, a FIFO or a device is not a CLAUDE.md to check (no read: no hang)
        lines = path.read_bytes().split(b"\n")
    except (FileNotFoundError, NotADirectoryError):
        return  # no file, as on base (a broken link included)
    except OSError as err:  # base never read it, so an unreadable file must not end the lint
        why = err.strerror or type(err).__name__
        report("WARN", path, "pointer-unread", f"not checked: {why}; fix: make it readable")
        return
    marks: list[tuple[int, str, str]] = []
    for n, line in enumerate(lines, 1):
        if n == 1:
            line = line.removeprefix(b"\xef\xbb\xbf")  # a UTF-8 byte-order mark is not text
        if m := POINTER_RE.fullmatch(line.rstrip()):
            marks.append((n, m[1].decode(), m[2].decode()))
    fix = "; fix: keep one begin line above one end line per harness and move stray markers out"
    for name in sorted({name for _, _, name in marks}):
        b = [n for n, kind, other in marks if other == name and kind == "begin"]
        e = [n for n, kind, other in marks if other == name and kind == "end"]
        if len(b) != 1 or len(e) != 1:
            msg = f"{name!r}: {len(b)} begin and {len(e)} end marker line(s), need one of each{fix}"
            report("ERROR", path, "pointer-marker", msg)
            continue
        if e[0] < b[0]:
            msg = f"{name!r}: end marker at line {e[0]} is above begin marker at line {b[0]}{fix}"
            report("ERROR", path, "pointer-marker", msg)
            continue
        inside = [(n, other) for n, _, other in marks if b[0] < n < e[0]]
        for n, other in inside:
            msg = f"{name!r}: line {n} holds a marker of {other!r} inside this block{fix}"
            report("ERROR", path, "pointer-marker", msg)
        size = len(b"\n".join(lines[b[0] - 1 : e[0]])) + (e[0] < len(lines))
        if not inside and size > POINTER_BUDGET:
            msg = f"{name!r}: block is {size} bytes, over {POINTER_BUDGET}"
            msg += "; fix: keep Goal and Trigger short and leave the change history below the block"
            report("WARN", path, "pointer-budget", msg)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not Path(argv[1]).is_dir():
        print("usage: lint_harness.py DIR  (DIR holds agents/ and/or skills/, e.g. .claude)")
        return 2
    root = Path(argv[1])
    agents = sorted(root.glob("agents/*.md"))
    skills = sorted(root.glob("skills/*/SKILL.md"))
    if not agents and not skills:
        report("ERROR", root, "empty", "no agents/*.md or skills/*/SKILL.md (pass the .claude dir)")
    today = datetime.now().astimezone().date()  # local calendar day
    names: set[str] = set()
    owners: dict[tuple[bool, str], list[Path]] = {}
    texts: dict[Path, str] = {}
    declared: set[tuple[str, str]] = set()
    for path in agents + skills:
        texts[path] = text = read(path)
        if (data := frontmatter(path, text)) is None:
            continue
        is_agent = path in agents
        keys, expect = (AGENT_KEYS, None) if is_agent else (SKILL_KEYS, path.parent.name)
        name = check_meta(path, data, keys, expect)
        if not is_agent:
            check_provenance(path, data, today)
        if name:
            owners.setdefault((is_agent, name), []).append(path)
        if is_agent:
            names.add(name)
            if "model" not in data:
                report("WARN", path, "model", "no model: field (choose one per agent)")
            elif "#" not in data["model"]:
                report("WARN", path, "model", "model: has no '# reason' comment")
            declared |= {(name, s) for s in connectors(path, text)}
    for path in sorted(set(root.glob("skills/**/SKILL.md")) - set(skills)):  # nested: line rules
        texts[path] = read(path)
    table = {row for text in texts.values() for row in preflight_rows(text)}
    for path, text in texts.items():
        for n, line in enumerate(text.splitlines(), 1):
            for ref in REF_RE.findall(line):
                if ref not in names and ref not in BUILTIN:
                    report("ERROR", path, "subagent-ref", f"line {n}: no agent file for {ref!r}")
            if v1 := V1_RE.search(line):
                report("ERROR", path, "v1-artefact", f"line {n}: {v1.group(0)}")
    for (is_agent, name), paths in sorted(owners.items()):  # same name, two files (C17)
        if len(paths) > 1:
            where = ", ".join(p.relative_to(root).as_posix() for p in paths)
            report(
                "ERROR",
                root,
                "duplicate-name",
                f"{'agent' if is_agent else 'skill'} {name!r} in {where}",
            )
    for path, text in texts.items():
        check_links(path, text)
        if path in skills:
            check_bundled(path, root, text)
    for path, text in texts.items():  # a brief that points back at earlier results (C6)
        if not SPAWN_RE.search(text):
            continue
        ln = last = 0
        for m in LAZY_RE.finditer(text):
            ln, last = ln + text.count("\n", last, m.start()), m.start()
            hit = " ".join(m.group(0).split())
            report("WARN", path, "lazy-delegation", f"line {ln + 1}: {hit!r}")
    for agent, server in sorted(declared - table):
        report("ERROR", root, "preflight", f"agent {agent!r} needs {server!r}: no preflight row")
    for agent, server in sorted(table - declared):
        report("ERROR", root, "preflight", f"row {agent} | {server} has no agent connector line")
    beside = Path(os.path.abspath(root))  # DIR's own links kept; a relative DIR joins getcwd()
    check_pointer((beside.parent if beside.name == ".claude" else beside) / "CLAUDE.md")
    errors = sum(line.startswith("ERROR") for line in out)
    print("\n".join(out + [f"lint_harness: {errors} error(s), {len(out) - errors} warning(s)"]))
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        code = main(sys.argv)
        if sys.stdout is not None:  # closed with >&-: print did nothing, so flush has nothing
            sys.stdout.flush()
    except BrokenPipeError:  # the reader hung up (| head -1): not a fault of ours
        sys.stdout = None  # so the exit-time flush cannot fail again
        code = 141  # 128 + SIGPIPE, the status a shell reports for a writer whose pipe closed
    sys.exit(code)
