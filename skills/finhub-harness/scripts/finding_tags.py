"""Check the cause tag and the drift row of recorded findings (quality-gates.md section 3-8).

Usage:
  finding_tags.py check FILE [FILE ...]

Records: a LESSON line (evolve report); a QA report (first line RESULT:), whose defect rows and
list items (numbered or bulleted; an `observation:` or `none` bullet is not one) under a heading that contains
Defects, in any heading form (quality-gates.md T2), need a cause tag and a file:line location, and whose drift row must
be well formed and must match the BASE line (the Base git token is not re-read; the exclude digest is
compared); a judge verdict (first line TOTALS:), whose REJECTED rows need a cause tag.

Lines inside code fences are not LESSON or drift records. A judge or QA record is read on every line,
fenced or not: a fenced table row, a fenced defect row or a fenced line that holds REJECTED is refused.
Before a verdict, a defect or a LESSON is read, each line is folded: HTML entities and tags are
resolved until nothing changes, format (Cf) and combining (Mn) characters are dropped, compatibility forms
are folded (NFKC), and the Cyrillic and Greek letters in FOLD_MAP are read as their Latin look-alikes. The drift row, the
CANDIDATE line and the BASE line are read exactly as written.

Every refusal exits 4, drift rows included (D1-D5): there is no advisory mode and no option that turns a
refusal into a pass (quality-gates 3-8). Exit 0: no refusal. 4: at least one refusal; one line per
refusal, FILE:LINE: message. 2: bad usage (any option), an unreadable file, or a file with no record.
A line whose entities do not settle within ENTITY_CAP passes refuses the record (fail closed).
Standard library only (re, sys, html, unicodedata, pathlib); no network, no subprocess; it reads recorded
text and never the repository.

adapted from references/openrig/docs/reference/wave-sdlc.md:54-62 (Apache-2.0): the drift question,
and the two miss causes (the spec lacked the context, or the context was in hand and the call was
still wrong). Rewritten in this repository's wording. The folding, the fence rule and FOLD_MAP are
NET-NEW (OR-D4 round 5): they close the character and fence routes that the judge found, and are not
from the OpenRig source.
"""

from __future__ import annotations

import html
import re
import sys
import unicodedata
from pathlib import Path

USAGE = "usage: finding_tags.py check FILE [FILE ...]"
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
TOKEN = re.compile(r"\bcause: (context-gap|judgment-gap)\b")
DEFECT = re.compile(r"^\s*[-*+|]\s*defect:\s*(.*)$")
# NET-NEW (OR-D4 fix round 2): the Defects route is an allow-list that fails closed (quality-gates T2). Outside a
# code fence, a line whose first word is defect or defects (after decoration is skipped) must be exactly one of the
# canonical forms below, or the record is refused; inside a read Defects section every non-blank line must be
# a canonical row, a continuation of one, an observation, or a none line.
ITEM = re.compile(r"^\s*(?:(\d+[.)])|[-*+])\s+(.*)$")
THEMATIC = re.compile(r"^\s*([-*_])(?:\s*\1){2,}\s*$")
FIRST_WORD = re.compile(r"^(?:\W|\d+[.)])*defects?(?![\w-])", re.IGNORECASE)
QUOTE = re.compile(r"^(?:[ \t]*>)+[ \t]?")
CANON_HEADING = re.compile(r"^#{2,3} Defects[ \t]*$")
CANON_ROW = re.compile(r"^- defect: (?=\S)")
CANON_NONE = re.compile(r"^Defects: none[ \t]*$")
NUMBERED = re.compile(r"^\d+[.)][ \t]+(.*)$")
PLAIN_NONE = re.compile(
    r"^(?:[-*+] )?\(?(?:none|none found|no defects found|n/a)\)?\.?[ \t]*$", re.IGNORECASE
)
OBSERVATION = re.compile(r"^- observation:", re.IGNORECASE)
CONTINUATION = re.compile(r"^(?: {2,}|\t)(?![-*+][ \t]|[|>#:]|\d+[.)](?:[ \t]|$))\S")
# Headings, every accepted form: `#` to `######` with any leading space (an ATX heading ends a section), `##Defects` with
# no space (it can open a section and never ends one), a setext heading (a text line over `===` or `---`), an
# HTML heading `<h1>` to `<h6>`, and a whole-line bold title (`**x**`, `__x__`, `<b>x</b>`, `<strong>x</strong>`).
HEADING = re.compile(r"^\s*(#{1,6})\s+(.*)$")
LOOSE_HEADING = re.compile(r"^\s*(#{1,6})(?=\S)(.*)$")
HTML_HEADING = re.compile(r"^\s*(?:<(?!h[1-6]\b)[a-z][^>]*>\s*)*<h([1-6])\b", re.IGNORECASE)
UNDERLINE = re.compile(r"^\s*(=+|-+)\s*$")
BOLD_TITLE = re.compile(r"^\s*(?:\*\*[^*]+\*\*|__[^_]+__)\s*:?\s*$")
HTML_BOLD = re.compile(r"^\s*<(b|strong)\b[^>]*>.*</\1>\s*:?\s*$", re.IGNORECASE)
ENTITY_CAP = 100
LOCATION = re.compile(r"^\S+:\d+(?:\s|$)")
# adapted from references/openrig/docs/reference/wave-sdlc.md:54-62 (Apache-2.0): a numbered item outside a Defects
# section is a defect row when it names a path and a line, read after bold and backtick markup is stripped.
PATH_LINE = re.compile(r"""^([^\s:]+):\d+(?:[\s:,.)\]"'-]|$)""")
PATH_LIKE = re.compile(r"/|\.[A-Za-z]")
RESULT = re.compile(r"^RESULT: (PASS|FAIL)(?: — (.*))?$")
PROCESS = (
    "candidate differs from the brief",
    "candidate moved during QA",
    "missing tool",
    "no git",
)
PROCESS_REASON = re.compile("(?:" + "|".join(re.escape(p) for p in PROCESS) + r")(?:$|[:;])")
CANDIDATE = re.compile(r"^CANDIDATE: (\S+)")
BASE = re.compile(r"^BASE: (git:[0-9a-f]{12}) excl=(none|[0-9a-f]{12})$")
ANY_TREE = re.compile(r"^(?:git:[0-9a-f]{12}\+[0-9a-f]{16}|files:[0-9a-f]{16})$")
GIT_TREE = re.compile(r"^git:[0-9a-f]{12}\+[0-9a-f]{16}$")
DRIFT = re.compile(r"^\s*\|\s*drift:\s*(.*?)\s*\|")
ENC = r"(?:[A-Za-z0-9._/~+-]|%[0-9A-F]{2})+"
DRIFT_BODY = re.compile(
    rf"declared=(\d+) changed=(\d+) undeclared=(-|{ENC}(?:,{ENC})*) "
    rf"flags=(\d+) excl=(none|[0-9a-f]{{12}}) on=(\S+)"
)
TOTAL = re.compile(r"REJECTED (\d+)")
# adapted from references/openrig/docs/reference/wave-sdlc.md:58-62 (Apache-2.0): a miss is disposed by cause.
# Markup characters are read as spaces, so `**Verdict:** REJECTED`, `~~REJECTED~~` and `UNVERIFIED_REJECTED`
# all hold the word; the word is bounded by non-letters, and the case is ignored. A markup character inside
# the word (`RE**JECT**ED`) is read as nothing, so that form holds the word too (NET-NEW, OR-D4 round 5).
MARKUP = re.compile(r"[*_`~]")
REJECTED_CELL = re.compile(r"(?<![A-Za-z])rejected(?![A-Za-z])", re.IGNORECASE)
TAG = re.compile(r"<[^<>]*>")
# NET-NEW (OR-D4 round 5): the Cyrillic and Greek letters that look like the Latin letters of REJECTED
# (E, C, T, J, D), in capitals and in the small forms that the case-blind word test reads: thirteen entries,
# the Greek lunate sigmas U+03F9 and U+03F2 included. They are translated before NFKD, which would turn them
# into sigma. The map is pinned by test_fold_map_is_the_pinned_set. Other look-alikes are not mapped (quality-gates 3-8, Does-not-cover):
# the letter R has no Cyrillic or Greek look-alike; U+13A1 (CHEROKEE LETTER E) looks like R and is not mapped.
FOLD_MAP = str.maketrans(
    {
        "Е": "E",
        "Ε": "E",
        "е": "e",  # Cyrillic capital IE, Greek capital epsilon, Cyrillic small ie
        "С": "C",
        "с": "c",  # Cyrillic capital and small es
        "\u03f9": "C",
        "\u03f2": "c",  # Greek capital and small lunate sigma (C-shaped)
        "Т": "T",
        "Τ": "T",  # Cyrillic capital te, Greek capital tau
        "Ј": "J",
        "ј": "j",  # Cyrillic capital and small je
        "Ԁ": "D",
        "ԁ": "d",  # Cyrillic capital and small komi de
    }
)
# NET-NEW (OR-D4 fix round 3): look-alikes of the letters d, e, f, c, t, s, read only by the Defects route (the word
# Defects and its row mark), so FOLD_MAP, the REJECTED reading and Daniel's residual 7 stay as they were. A look-alike
# that is not listed here is caught by lookalike() below, which fails closed. Pinned by test_defect_fold_is_the_pinned_set.
_LOOKALIKES = {
    "d": "\u1d05\u00f0\u0111\u0256\u0257",  # small capital D, eth, d with stroke, african d, d with hook
    "D": "\u00d0\u0110",  # capital eth, D with stroke
    "e": "\u1d07\u025b\u03b5\u0454\u04bd",  # small capital E, open e, epsilon, Ukrainian ie, e with descender
    "E": "\u0190\u0404",  # open E, Ukrainian capital ie
    "f": "\u0192\ua730\u03dd",  # f with hook, small capital F, digamma
    "F": "\u0191\u03dc",  # F with hook, capital digamma
    "c": "\u1d04\u0188",  # small capital C, c with hook
    "C": "\u0187",  # C with hook
    "t": "\u1d1b\u01ab\u01ad\u0167\u03c4\u0442",  # small capital T, t with hook (two), t with stroke, tau, te
    "T": "\u0166",  # T with stroke
    "s": "\u0455\ua731\u01bd\u0282",  # Cyrillic dze, small capital S, tone five, s with hook
    "S": "\u0405\u01a7",  # Cyrillic capital dze, S with hook
}
DEFECT_FOLD = {ord(c): letter for letter, chars in _LOOKALIKES.items() for c in chars}
# every control character (Cc) but the tab: NUL and its kin are read as nothing in the Defects route
DROP_CONTROL = {c: None for c in [*range(9), *range(11, 32), *range(127, 160)]}
WORD = re.compile(r"[^\W_]+")

Refusal = tuple[bool, str]  # (is a drift-row refusal, message); the flag is a label, not a switch
FENCED_ROW = (
    "fenced table row in a judge or QA record (a fence may not hold a verdict or drift row)"
)
FENCED_DEFECT = "fenced defect row in a judge or QA record (a fence may not hide a defect)"
NON_CANONICAL = (
    "non-canonical Defects line (a line that starts with defect or defects is `## Defects`, "
    "`### Defects`, `- defect: file:line ...` or `Defects: none`)"
)
NON_CANONICAL_ROW = (
    "non-canonical line in a Defects section (a defect row, a continuation, an observation, "
    "a none line or a fence)"
)


OUTSIDE = (
    "numbered file:line row sits outside a Defects section but is a defect row: tag it with "
    "`cause: context-gap` or `cause: judgment-gap`, or move it to bullets, a table or a code fence"
)
OPEN_FENCE = "code fence opened here is never closed by a matching closer (record refused)"


class Usage(Exception):
    """Bad input: exit 2."""


class Line:
    """One line of a record: the raw text, and the two folded readings of it (see forms)."""

    def __init__(self, no: int, raw: str, kept: str, text: str, fenced: bool) -> None:
        self.no = no
        self.raw = raw
        self.kept = kept  # folded, with tags left in
        self.text = text  # folded, with tags removed: the reading the rules use
        self.fenced = fenced


class Unresolved(Exception):
    """A line whose entities or tags did not settle within ENTITY_CAP passes: the record is refused."""


def _unescape(text: str) -> str:
    """HTML entities, decimal and hex, resolved until nothing changes (each change shortens the text).

    A line that is still changing after ENTITY_CAP passes has not settled: Unresolved (the record is refused).
    """
    # up to ENTITY_CAP passes that change the text, then one pass that confirms nothing changes
    for _ in range(ENTITY_CAP + 1):
        nxt = html.unescape(text)
        if nxt == text:
            return text
        text = nxt
    raise Unresolved


def _fold(text: str) -> str:
    """Pinned look-alikes, compatibility form, no Cf or Mn characters (NET-NEW, OR-D4 round 5).

    The look-alikes are translated first and last: NFKD turns U+03F9 and U+03F2 into sigma."""
    text = unicodedata.normalize("NFKD", text.translate(FOLD_MAP))
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cf", "Mn"))
    return unicodedata.normalize("NFKC", text).translate(FOLD_MAP)


def forms(raw: str) -> tuple[str, str]:
    """(tags kept, tags removed): the two folded readings of one line. A verdict is read in both."""
    kept = _fold(_unescape(raw))
    text = _unescape(raw)
    # a tag can hide an entity and an entity can spell a tag: repeat to a fixed point (same cap as _unescape)
    for _ in range(ENTITY_CAP + 1):
        nxt = _unescape(TAG.sub("", text))
        if nxt == text:
            return kept, _fold(text)
        text = nxt
    raise Unresolved


def scan(raw_lines: list[str]) -> tuple[list[Line], int]:
    """(lines, number of the line that opened a fence still open at the end, or 0).

    Every line carries its readings and its fence state; a fence line is fenced. A fence that is never closed
    by a matching closer hides every later line, so the caller refuses the record (OR-D4 fix round 3).
    """
    out: list[Line] = []
    fence = ""
    opened = 0
    for n, raw in enumerate(raw_lines, 1):
        try:
            kept, text = forms(raw)
        except Unresolved:
            raise Unresolved(n) from None
        m = FENCE.match(text)
        if fence:
            fenced = True
            s = text.strip()
            if m and s == fence[0] * len(s) and len(s) >= len(fence):
                fence = ""
        elif m:
            fence = m.group(1)
            opened = n
            fenced = True
        else:
            fenced = False
        out.append(Line(n, raw, kept, text, fenced))
    return out, (opened if fence else 0)


def is_row(line: Line) -> bool:
    """A line with a pipe, leading pipe or not, in either reading (the full-width bar folds to the pipe)."""
    return "|" in line.kept or "|" in line.text


def rejected_cells(reading: str) -> int:
    """Cells of one reading in which the word REJECTED appears; markup is read as a space, or as nothing."""
    n = 0
    for cell in reading.split("|"):
        if REJECTED_CELL.search(MARKUP.sub(" ", cell)) or REJECTED_CELL.search(
            MARKUP.sub("", cell)
        ):
            n += 1
    return n


def rejected_count(line: Line) -> int:
    """The larger of the two readings' counts, so a tag cannot hide a cell from the total (NET-NEW)."""
    return max(rejected_cells(line.kept), rejected_cells(line.text))


def fenced_row(line: Line) -> bool:
    """A fenced markdown table row (leading and trailing pipe), or a fenced line that holds REJECTED in a row."""
    s = line.text.strip()
    return (s.startswith("|") and s.endswith("|")) or (is_row(line) and rejected_count(line) > 0)


def one_cause(text: str) -> bool:
    """Exactly one well-formed cause tag on the line, and no second `cause:` of any value."""
    return len(TOKEN.findall(text)) == 1 and text.count("cause:") == 1


def heading(scanned: list[Line], i: int) -> tuple[int, str, bool, bool] | None:
    """(level, text, can end a section, setext) when line i, which is not inside a fence, is a heading of any form.

    Quote markers are dropped first, so a quoted heading is read like any other."""
    line = scanned[i]
    kept, text = QUOTE.sub("", line.kept), QUOTE.sub("", line.text)
    if (h := HTML_HEADING.match(kept)) is not None:
        return int(h.group(1)), text, True, False
    if (m := HEADING.match(text)) is not None:
        return len(m.group(1)), m.group(2), True, False
    if (m := LOOSE_HEADING.match(text)) is not None:
        return len(m.group(1)), m.group(2), False, False
    nxt = scanned[i + 1] if i + 1 < len(scanned) else None
    if nxt is not None and (u := UNDERLINE.match(nxt.text)) is not None:
        # a defect row over a dash line is a row, never a heading: it would end a Defects section (fix round 2)
        t = text
        if t.strip() and not (
            UNDERLINE.match(t) or THEMATIC.match(t) or ITEM.match(t) or DEFECT.match(t) or "|" in t
        ):
            return (1 if u.group(1)[0] == "=" else 2), t, True, True
    return None


def near(a: str, b: str) -> bool:
    """Edit distance at most 1 (one insertion, deletion or substitution)."""
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1 :] or a[i + 1 :] == b[i + 1 :]


def lookalike(token: str) -> bool:
    """A word with a non-ASCII letter whose ASCII letters alone are within one edit of defect or defects.

    Fail closed for a look-alike that DEFECT_FOLD does not list (`Dɛfects`, `deƒect`, `Defectѕ`)."""
    if token.isascii():
        return False
    skeleton = "".join(ch for ch in token if ch.isascii()).lower()
    return near(skeleton, "defect") or near(skeleton, "defects")


def first_word_lookalike(text: str) -> bool:
    """The first word of the line (decoration skipped, as FIRST_WORD does) is a look-alike of defect or defects."""
    for reading in (text, MARKUP.sub("", text)):
        m = re.match(r"(?:\W|\d+[.)])*([^\W_]+)", reading)
        if m is not None and lookalike(m.group(1)):
            return True
    return False


def names_defects(text: str) -> bool:
    """The title names defects: the word, or a look-alike word, anywhere in it."""
    return "defects" in text.lower() or any(lookalike(w) for w in WORD.findall(text))


def names_path_line(body: str) -> bool:
    """True when an item starts with a path-like token and a line number (`12:30`, `host:80`, `exit:0` are not)."""
    m = PATH_LINE.match(MARKUP.sub("", body).lstrip("([\"' \t"))
    return bool(m and PATH_LIKE.search(m.group(1)))


def starts_with_defect(text: str) -> bool:
    """True when the line, with quote markers, heading marks, list marks and markup skipped, starts with the
    word defect or defects. Markup is read as a space and as nothing (`Def**ects**` holds the word).
    """
    return bool(FIRST_WORD.match(text) or FIRST_WORD.match(MARKUP.sub("", text)))


def is_canonical(text: str) -> bool:
    return bool(CANON_HEADING.match(text) or CANON_ROW.match(text) or CANON_NONE.match(text))


def defect_route(name: str, scanned: list[Line], fail: bool) -> tuple[list[Refusal], list[int]]:
    """(refusals, line numbers of defect rows) for the Defects route of a QA report (quality-gates T2).

    Allow-list, fail closed: a line outside a fence that starts with defect or defects is canonical or refused;
    inside a Defects section every non-blank line is a defect row, a continuation, an observation, a none line or a
    fence, or the record is refused. A heading of the same or a higher level ends the section."""
    out: list[Refusal] = []
    defects: list[int] = []
    in_sec, level, held, prev_ok, start, underline = False, 0, 0, False, 0, -1

    def read(s: str) -> str:
        return s.translate(DEFECT_FOLD).translate(DROP_CONTROL)

    scanned = [Line(x.no, x.raw, read(x.kept), read(x.text), x.fenced) for x in scanned]

    def close_section() -> None:
        if in_sec and fail and held == 0:
            out.append(
                (False, f"{name}:{start}: Defects section holds no defect row and no none line")
            )

    for i, line in enumerate(scanned):
        t = line.text
        outside = False
        if i == underline:  # the underline of a setext heading is part of the heading
            continue
        if line.fenced:
            prev_ok = False
            if fenced_row(line):
                out.append((False, f"{name}:{line.no}: {FENCED_ROW}"))
            d = DEFECT.match(t)
            it = ITEM.match(t) if in_sec else None
            if d is not None:
                body = d.group(1)
                out.append((False, f"{name}:{line.no}: {FENCED_DEFECT}"))
            elif it is not None and it.group(1) is not None:
                body = it.group(2)
            else:
                continue
        else:
            if (starts_with_defect(t) and not is_canonical(line.kept)) or first_word_lookalike(t):
                out.append((False, f"{name}:{line.no}: {NON_CANONICAL}"))
            if (h := heading(scanned, i)) is not None and (not in_sec or (h[2] and h[0] <= level)):
                close_section()
                in_sec, level, held, prev_ok, start = (
                    names_defects(h[1]),
                    h[0],
                    0,
                    False,
                    line.no,
                )
                underline = i + 1 if h[3] else -1
                continue
            if not in_sec and (BOLD_TITLE.match(t) or HTML_BOLD.match(line.kept)):
                # a bold title can open a section; a heading ends it
                if names_defects(t):
                    in_sec, level, held, prev_ok, start = True, 7, 0, False, line.no
                continue
            d = DEFECT.match(t)
            n = NUMBERED.match(t)
            if n is not None and not in_sec:
                # a path and a line make it a defect row anywhere
                outside = names_path_line(n.group(1))
                if not outside:
                    n = None  # an ordinary numbered list item
            if d is not None:
                body = d.group(1)
            elif n is not None:
                body = n.group(1)
            else:
                if in_sec and t.strip():
                    if CANON_NONE.match(t) or PLAIN_NONE.match(t):
                        held += 1
                        prev_ok = True
                    elif OBSERVATION.match(t) or (prev_ok and CONTINUATION.match(t)):
                        prev_ok = True
                    else:
                        prev_ok = False
                        out.append((False, f"{name}:{line.no}: {NON_CANONICAL_ROW}"))
                continue
        defects.append(line.no)
        held += 1
        prev_ok = True
        if not one_cause(t):
            out.append((False, f"{name}:{line.no}: defect row without exactly one cause tag"))
        if outside:
            if not fail:
                out.append((False, f"{name}:{line.no}: {OUTSIDE}"))
        elif not LOCATION.match(body):
            out.append((False, f"{name}:{line.no}: defect row without a file:line location"))
    close_section()
    return out, defects


def check_lessons(name: str, live: list[Line]) -> tuple[list[Refusal], int]:
    out: list[Refusal] = []
    count = 0
    for line in live:
        if line.text.startswith("LESSON |"):
            count += 1
            if not one_cause(line.text):
                out.append((False, f"{name}:{line.no}: LESSON without exactly one cause tag"))
    return out, count


def check_qa(name: str, lines: list[str], scanned: list[Line]) -> tuple[list[Refusal], int]:
    """(refusals, defect rows) for a QA report whose first line is RESULT:."""
    m = RESULT.match(scanned[0].text)
    if m is None:
        return [
            (False, f"{name}:1: RESULT line is not PASS, bare FAIL, or FAIL with a process reason")
        ], 0
    verdict, reason = m.group(1), m.group(2)
    out: list[Refusal] = []
    if verdict == "PASS" and reason is not None:
        out.append((False, f"{name}:1: PASS line carries a reason"))
    if verdict == "FAIL" and reason is not None and not PROCESS_REASON.match(reason):
        out.append(
            (False, f"{name}:1: FAIL reason is not a process reason; a defect needs a defect row")
        )
    refusals, defects = defect_route(name, scanned, verdict == "FAIL")
    out += refusals
    token = next(
        (
            c.group(1)
            for ln in lines[1:3]
            if (c := CANDIDATE.match(ln)) and ANY_TREE.match(c.group(1))
        ),
        None,
    )
    if token is None:
        return out + [(False, f"{name}:2: no CANDIDATE line naming a git: or files: tree")], len(
            defects
        )
    bare = verdict == "FAIL" and reason is None
    if bare and not defects:
        out.append((False, f"{name}:1: bare FAIL with no defect row"))
    if verdict == "PASS" and defects:
        out.append((False, f"{name}:1: PASS with defect rows ({len(defects)}); a PASS holds none"))
    if verdict == "PASS" and not GIT_TREE.match(token):
        out.append((False, f"{name}:2: PASS needs a git: candidate (files: cannot PASS)"))
    needs_drift = verdict == "PASS" or bare
    base = next((b for ln in lines[1:4] if (b := BASE.match(ln))), None)
    rows = [
        (line.no, d.group(1))
        for line in scanned
        if not line.fenced and (d := DRIFT.match(line.raw))
    ]
    if needs_drift and len(rows) != 1:
        out.append((True, f"{name}:1: drift row missing or repeated ({len(rows)} found)"))
    if needs_drift and base is None:
        out.append(
            (
                True,
                (
                    f"{name}:1: no BASE line (`BASE: git:<12 hex> excl=<12 hex or none>`) "
                    "to check the drift row against"
                ),
            )
        )
    for no, body in rows:
        fields = DRIFT_BODY.fullmatch(body)
        if fields is None:
            out.append(
                (
                    True,
                    (
                        f"{name}:{no}: drift row malformed: needs declared=N changed=N undeclared=LIST|- "
                        "flags=N excl=HEX|none on=git:TREE (paths comma-separated, percent-encoded, no spaces)"
                    ),
                )
            )
            continue
        _, changed, undeclared, flags, excl, on = fields.groups()
        if not GIT_TREE.match(on):
            out.append(
                (
                    True,
                    f"{name}:{no}: drift row on= is not a git: token (files: and unborn are refused)",
                )
            )
        elif on != token:
            out.append((True, f"{name}:{no}: drift row names another candidate ({on})"))
        if verdict == "PASS" and undeclared != "-":
            out.append((True, f"{name}:{no}: PASS with undeclared paths: {undeclared}"))
        if undeclared != "-" and len(undeclared.split(",")) > int(changed):
            out.append((True, f"{name}:{no}: undeclared list longer than changed={changed}"))
        if verdict == "PASS" and flags != "0":
            out.append(
                (
                    True,
                    f"{name}:{no}: PASS with index flags set ({flags} path(s) not H in ls-files -v)",
                )
            )
        if base is not None and excl != base.group(2):
            out.append(
                (
                    True,
                    (
                        f"{name}:{no}: drift row excl={excl} differs from the Base line "
                        f"(excl={base.group(2)}): .git/info/exclude changed since Base"
                    ),
                )
            )
    return out, len(defects)


def check_judge(name: str, scanned: list[Line]) -> tuple[list[Refusal], int]:
    """(refusals, REJECTED rows) for a judge verdict whose first line is TOTALS:. Every line is read."""
    t = TOTAL.search(scanned[0].text)
    if t is None:
        return [(False, f"{name}:1: TOTALS line has no REJECTED count")], 0
    out: list[Refusal] = []
    rows = 0
    cells = 0
    for line in scanned[1:]:  # the TOTALS line is not a row; a row may lack a leading pipe
        if not is_row(line):
            continue
        if line.fenced and fenced_row(line):
            out.append((False, f"{name}:{line.no}: {FENCED_ROW}"))
        c = rejected_count(line)
        if c == 0:
            continue
        rows += 1
        cells += c
        if not one_cause(line.text):
            out.append((False, f"{name}:{line.no}: REJECTED row without exactly one cause tag"))
    if cells != int(t.group(1)):
        out.append(
            (
                False,
                f"{name}:1: TOTALS says REJECTED {t.group(1)} but the tables hold {cells} REJECTED cell(s)",
            )
        )
    return out, rows


def check_text(name: str, text: str) -> tuple[list[Refusal], int]:
    raw_lines = text.splitlines()
    try:
        scanned, opened = scan(raw_lines)
    except Unresolved as e:
        return [
            (
                False,
                (
                    f"{name}:{e.args[0]}: entities or tags do not settle in {ENTITY_CAP} passes; "
                    "record refused"
                ),
            )
        ], 1
    out: list[Refusal] = []
    count = 0
    if opened:
        out.append((False, f"{name}:{opened}: {OPEN_FENCE}"))
        count += 1
    if scanned and scanned[0].text.startswith("RESULT:"):
        r, d = check_qa(name, raw_lines, scanned)
        out += r
        count += 1 + d
    elif scanned and scanned[0].text.startswith("TOTALS:"):
        r, d = check_judge(name, scanned)
        out += r
        count += 1 + d
    r, n = check_lessons(name, [line for line in scanned if not line.fenced])
    out += r
    count += n
    if count == 0:
        raise Usage(
            f"{name}: no record in file (a QA report starts RESULT:, a verdict TOTALS:, "
            "an evolve report has LESSON lines)"
        )
    return out, count


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "check":
        print(USAGE, file=sys.stderr)
        return 2
    args = argv[2:]
    if not args or any(a.startswith("-") for a in args):
        print(USAGE, file=sys.stderr)
        return 2
    refused: list[str] = []
    records = 0
    for arg in args:
        try:
            text = Path(arg).read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"finding_tags: cannot read {arg}: {e}", file=sys.stderr)
            return 2
        try:
            got, count = check_text(arg, text)
        except Usage as e:
            print(f"finding_tags: {e}", file=sys.stderr)
            return 2
        records += count
        refused.extend(msg for _, msg in got)
    for line in refused:
        print(line)
    print(f"finding_tags: {records} record(s), {len(refused)} refused")
    return 4 if refused else 0


if __name__ == "__main__":
    try:
        code = main(sys.argv)
        if sys.stdout is not None:  # closed with >&-: print did nothing, so flush has nothing
            sys.stdout.flush()
    except BrokenPipeError:  # the reader hung up (| head -1): not a fault of ours
        sys.stdout = None  # so the exit-time flush cannot fail again
        code = 141  # 128 + SIGPIPE, the status a shell reports for a writer whose pipe closed
    sys.exit(code)
