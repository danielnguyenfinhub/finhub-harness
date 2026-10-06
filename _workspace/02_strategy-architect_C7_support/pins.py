"""pins.py <SKILL.md>: whole-line pins for the C7 insertions. Exit 0 if all hold, 1 otherwise (prints each failure).
 1. every original line is still there, in order (nothing deleted or reworded)
 2. every inserted line occurs as a whole line exactly as often as inserted (the grep -cxF check)
 3. nothing else was added: the line count is the expected one and every line is original or inserted
"""
import sys
from pathlib import Path
here = Path(__file__).resolve().parent
orig = (here.parent / "orig/skills/finhub-harness-evolve/SKILL.md").read_text(encoding="utf-8").split("\n")
ins = [l for l in (here / "inserted_lines.txt").read_text(encoding="utf-8").split("\n") if l]
got = Path(sys.argv[1]).read_text(encoding="utf-8").split("\n")
fails = []
it = iter(got)
for o in orig:
    if not any(o == g for g in it):
        fails.append(f"original line lost or moved: {o[:70]!r}"); break
for l in sorted(set(ins)):
    n, want = got.count(l), ins.count(l)
    if n != want:
        fails.append(f"inserted line count {n} (want {want}): {l[:70]!r}")
known = set(orig) | set(ins) | {""}
extra = [g for g in got if g not in known]
if extra:
    fails.append(f"{len(extra)} unknown line(s): {extra[0][:70]!r}")
want_len = int((here / "expected_len.txt").read_text())
if len(got) != want_len:
    fails.append(f"line count {len(got)} (expected {want_len})")
print("\n".join(fails) if fails else "pins ok")
sys.exit(1 if fails else 0)
