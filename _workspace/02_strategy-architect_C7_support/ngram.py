"""8-word verbatim-run check: added lines of the evolve SKILL.md vs every file under the cited reference directories.
Usage: ngram.py <orig-root> <new-root> [references-root]. '8-gram hits: 0' is the pass condition (a 7-gram run is allowed)."""
import re, sys
from pathlib import Path
R = Path(sys.argv[3] if len(sys.argv) > 3 else "/home/user/finhub-harness/references")
srcs = [R/"openharness/src/openharness/skills/bundled/content", R/"openharness/src/openharness/services/autodream", R/"openharness/src/openharness/memory",
        R/"autogpt/classic/direct_benchmark", R/"autogpt/classic/original_autogpt/autogpt/agents/prompt_strategies",
        R/"deepseek_harness/.agents", R/"crewai/lib/crewai/src/crewai/crew.py"]
tok = lambda s: re.findall(r"[a-z0-9']+", s.lower())
grams, nfiles = set(), 0
for s in srcs:
    for f in ([s] if s.is_file() else [x for x in s.rglob("*") if x.is_file() and x.suffix in (".py", ".ts", ".md", ".tsx")]):
        nfiles += 1; w = tok(f.read_text(errors="replace")); grams |= {" ".join(w[i:i+8]) for i in range(len(w) - 7)}
fn = "skills/finhub-harness-evolve/SKILL.md"
orig, new = Path(sys.argv[1]), Path(sys.argv[2])
a = set((orig / fn).read_text().split("\n"))
added = "\n".join(l for l in (new / fn).read_text().split("\n") if l not in a)
w = tok(added); hits = 0
for i in range(len(w) - 7):
    if " ".join(w[i:i+8]) in grams:
        hits += 1; print("HIT", " ".join(w[i:i+8]))
print(f"files scanned: {nfiles}; added words: {len(w)}; 8-gram hits: {hits}")
