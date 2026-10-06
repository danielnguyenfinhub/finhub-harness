"""8-word verbatim-run check: inserted prose vs the cited reference files. Usage: ngram.py <orig-root> <new-root>.
Prints HIT lines; '8-gram hits: 0' is the pass condition."""
import re, sys
from pathlib import Path
R = Path("/home/user/finhub-harness/references")
srcs = [R/"openharness/src/openharness/coordinator", R/"openharness/src/openharness/autopilot/service.py",
        R/"deepseek_harness/packages/goal", R/"deepseek_harness/packages/workflow", R/"openhands/src/api",
        R/"crewai/lib/crewai/src/crewai/task.py", R/"crewai/lib/crewai/src/crewai/project/crew_base.py",
        R/"crewai/lib/crewai/src/crewai/crew.py", R/"crewai/lib/crewai/src/crewai/utilities/guardrail.py"]
tok = lambda s: re.findall(r"[a-z0-9']+", s.lower())
grams = set()
for s in srcs:
    for f in ([s] if s.is_file() else [x for x in s.rglob("*") if x.is_file() and x.suffix in (".py", ".ts", ".md", ".tsx")]):
        w = tok(f.read_text(errors="replace")); grams |= {" ".join(w[i:i+8]) for i in range(len(w) - 7)}
orig, new = Path(sys.argv[1]), Path(sys.argv[2])
hits = 0
for fn in ["skills/finhub-harness/SKILL.md", "skills/finhub-harness/references/surfaces.md", "skills/finhub-harness/references/orchestrator-template.md"]:
    a = set((orig / fn).read_text().split("\n"))
    added = "\n".join(l for l in (new / fn).read_text().split("\n") if l not in a)
    w = tok(added)
    for i in range(len(w) - 7):
        if " ".join(w[i:i+8]) in grams: hits += 1; print("HIT", fn, " ".join(w[i:i+8]))
print("8-gram hits:", hits)
