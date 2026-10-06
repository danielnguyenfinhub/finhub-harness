"""Writes the four live-mutant skill files (LMB backup, LMS secret, LML layer, LME evidence) next to this script's parent in mutants/."""
from pathlib import Path
here = Path(__file__).resolve().parent
base = (here.parent / "new/skills/finhub-harness-evolve/SKILL.md").read_text(encoding="utf-8")
out = here.parent / "mutants"; out.mkdir(exist_ok=True)
def span(t, start, end):
    s = t.index(start); e = t.index(end, s) + len(end); return t[:s] + t[e:]
def rep(t, old, new):
    assert t.count(old) == 1, old[:50]; return t.replace(old, new)
# LMB: the backup rule deleted everywhere (gate, Phase 4 backups check, Phase 5 backups bullet)
b = span(base, "**Backup gate (before the first edit).**", "\n\n")
b = span(b, "   - Backups: `ls <file>.bak*`", "\n")
b = span(b, "- Backups: for each edited file, its backup path", "\n")
b = rep(b, "(it may be the only copy", "(it may be the only copy") if False else b
# LMS: the secret rule deleted everywhere (step 5, Phase 4 secrets check, Phase 5 intro and bullet)
s = base[:base.index("5. **Quote safely.**")] + base[base.index("6. **Open the evidence"):]
s = span(s, "   - Secrets: once the report file exists", "does not remove it.\n")
s = span(s, "Write the report to `_workspace/evolve-report.md`", "\n\n")
s = span(s, "- Secret check: what the Phase 4 grep printed", "\n")
# LML: the governance rule inverted and its table row deleted
l = rep(base, "is governance, not execution.", "is execution, not governance.")
l = span(l, "| governance | a rule, gate", "\n")
# LME: the evidence rule deleted (step 6, the no-evidence arm of unclassified, the fix:none sentence)
e = span(base, "6. **Open the evidence before you form a lesson.**", "\n")
e = rep(e, "A failure that fits no layer, or has no evidence you opened, is", "A failure that fits no layer is")
e = rep(e, ", using the evidence from Phase 1 step 6", "")
o = rep(base, "If `<file>.bak` already exists, leave it alone (it may be the only copy from before an earlier evolve) and use the first unused `<file>.bak.2`, `<file>.bak.3` and so on.", "If `<file>.bak` already exists, overwrite it.")
for name, t in (("LMO", o), ("LMB", b), ("LMS", s), ("LML", l), ("LME", e)):
    assert t != base
    (out / f"{name}.md").write_text(t, encoding="utf-8")
    print(name, len(t.splitlines()), "lines")
