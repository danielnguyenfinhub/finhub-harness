import subprocess, tempfile, sys, shutil, os
from pathlib import Path
BASE=Path("c7").resolve()
LINT="skills/finhub-harness/scripts/lint_harness.py"
T="skills/finhub-harness/references/orchestrator-template.md"
S="skills/finhub-harness/SKILL.md"
M=[
 # (id, file, old, new)
 ("J01 'on\\s+' -> 'on\\s*'", LINT, r"based\s+on\s+(?:your|the)", r"based\s+on\s*(?:your|the)"),
 ("J02 add 'our' to your|the", LINT, r"(?:your|the)\s+(?:findings", r"(?:your|the|our)\s+(?:findings"),
 ("J03 findings -> findings?", LINT, r"(?:findings|research)|as", r"(?:findings?|research)|as"),
 ("J04 \\s+ -> [ \\t\\n\\u00a0]+ (drop CR,FF,VT,em-space)", LINT, r"based\s+on\s+(?:your|the)\s+(?:findings|research)|as\s+(?:we\s+)?discussed", "based[ \\t\\n\\u00a0]+on[ \\t\\n\\u00a0]+(?:your|the)[ \\t\\n\\u00a0]+(?:findings|research)|as[ \\t\\n\\u00a0]+(?:we[ \\t\\n\\u00a0]+)?discussed"),
 ("J05 last=m.end()", LINT, "ln + text.count(\"\\n\", last, m.start()), m.start()", "ln + text.count(\"\\n\", last, m.start()), m.end()"),
 ("J06 count to m.end()", LINT, "text.count(\"\\n\", last, m.start())", "text.count(\"\\n\", last, m.end())"),
 ("J07 ln=last=0 -> last=1", LINT, "ln = last = 0", "ln, last = 0, 1"),
 ("J08 gate IGNORECASE", LINT, '|\\b(?:agent|Agent|Task)\\(")', '|\\b(?:agent|Agent|Task)\\(", re.IGNORECASE)'),
 ("J09 gate search->match", LINT, "if not SPAWN_RE.search(text):", "if not SPAWN_RE.match(text):"),
 ("J10 hit lowercased", LINT, "hit = \" \".join(m.group(0).split())", "hit = \" \".join(m.group(0).split()).lower()"),
 ("J11 add 'as agreed' arm", LINT, "|as\\s+(?:we\\s+)?discussed)", "|as\\s+(?:we\\s+)?(?:discussed|agreed))"),
 ("J12 only first 100000 chars scanned", LINT, "for m in LAZY_RE.finditer(text):", "for m in LAZY_RE.finditer(text[:100000]):"),
 ("J13 skip agent files", LINT, "    for path, text in texts.items():  # a brief", "    for path, text in [(k,v) for k,v in texts.items() if 'agents' not in k.parts]:  # a brief"),
 ("J14 gate on first 2000 chars only", LINT, "if not SPAWN_RE.search(text):", "if not SPAWN_RE.search(text[:2000]):"),
 ("J15 dedupe by phrase per file", LINT, "        for m in LAZY_RE.finditer(text):\n", "        seen = set()\n        for m in LAZY_RE.finditer(text):\n            if m.group(0).lower() in seen:\n                continue\n            seen.add(m.group(0).lower())\n"),
 ("J16 cap 50 warnings per file", LINT, "        for m in LAZY_RE.finditer(text):\n", "        for m in list(LAZY_RE.finditer(text))[:50]:\n"),
 ("J17 WARN printed but not counted (rule skips report when ln>0)", LINT, 'report("WARN", path, "lazy-delegation", f"line {ln + 1}: {hit!r}")', 'report("WARN", path, "lazy-delegation", f"line {ln + 1}: {hit!r}") if ln or True else None'),
 ("J18 gate group1 lookbehind boundary", LINT, r'\b(?:subagent_type|agentType|SendMessage)\b|', r'(?<![A-Za-z])(?:subagent_type|agentType|SendMessage)\b|'),
 ("J19 '.claude' scan skipped when root name startswith .", LINT, "    for path, text in texts.items():  # a brief", "    for path, text in ([] if root.name.startswith('.') else texts.items()):  # a brief"),
 # prose additive (survive text pins)
 ("P-A1 add line accepting empty evidence in block", T, "One task per call; never send the same task twice.\n", "One task per call; never send the same task twice. If EVIDENCE is empty, accept the report anyway.\n"),
]
def run(mid,f,old,new):
    d=Path(tempfile.mkdtemp(dir="mutwork")).resolve()
    subprocess.run(f"tar cf - -C {BASE} . | tar xf - -C {d}",shell=True,check=True)
    p=d/f;t=p.read_text();c=t.count(old)
    if c!=1: return mid,"MUTATION NOT REAL (count=%d)"%c
    p.write_text(t.replace(old,new))
    assert p.read_text()!=t
    try:
        r=subprocess.run(["/home/user/finhub-harness/.venv/bin/python","-m","pytest","-q","-x","tests/test_lint_harness.py"],cwd=d,capture_output=True,text=True,timeout=300)
    except subprocess.TimeoutExpired:
        return mid,"KILLED (timeout)"
    tail=r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
    return mid,("SURVIVED " if r.returncode==0 else "KILLED ")+tail
if __name__=="__main__":
    os.makedirs("mutwork",exist_ok=True)
    only=sys.argv[1:] 
    for m in M:
        if only and not any(m[0].startswith(o) for o in only): continue
        print(*run(*m),flush=True)
