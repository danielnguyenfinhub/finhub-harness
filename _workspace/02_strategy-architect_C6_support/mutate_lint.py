import shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).parent
LINT = "skills/finhub-harness/scripts/lint_harness.py"
src = (ROOT / LINT).read_text()
M = [
 ("L01 drop 'findings'", "(?:findings|research)", "(?:research)"),
 ("L02 drop 'research'", "(?:findings|research)", "(?:findings)"),
 ("L03 drop 'your'", "(?:your|the)", "(?:the)"),
 ("L04 drop 'the'", "(?:your|the)", "(?:your)"),
 ("L05 drop 'we' optional", "as\\s+(?:we\\s+)?discussed", "as\\s+discussed"),
 ("L06 drop 'as ... discussed' arm", "|as\\s+(?:we\\s+)?discussed)", ")"),
 ("L07 drop 'based on' arm", "based\\s+on\\s+(?:your|the)\\s+(?:findings|research)|", ""),
 ("L08 no IGNORECASE", "    re.IGNORECASE,\n", "    0,\n"),
 ("L09 \\s+ -> single space (as)", "as\\s+(?:we\\s+)?discussed", "as (?:we )?discussed"),
 ("L10 \\s+ -> ' +' everywhere", "based\\s+on\\s+(?:your|the)\\s+(?:findings|research)", "based +on +(?:your|the) +(?:findings|research)"),
 ("L10b \\s -> [ \\t] (no wrap)", "based\\s+on\\s+(?:your|the)\\s+(?:findings|research)|as\\s+(?:we\\s+)?discussed", "based[ \\t]+on[ \\t]+(?:your|the)[ \\t]+(?:findings|research)|as[ \\t]+(?:we[ \\t]+)?discussed"),
 ("L11 drop leading \\b", 'r"\\b(?:based', 'r"(?:based'),
 ("L12 drop trailing \\b", 'discussed)\\b",', 'discussed)",'),
 ("L13 WARN -> ERROR", 'report("WARN", path, "lazy-delegation"', 'report("ERROR", path, "lazy-delegation"'),
 ("L14 no spawn gate", "        if not SPAWN_RE.search(text):\n            continue\n", ""),
 ("L15 gate drops agentType", 'SPAWN_RE = re.compile(r"\\b(?:subagent_type|agentType|SendMessage)', 'SPAWN_RE = re.compile(r"\\b(?:subagent_type|SendMessage)'),
 ("L16 gate drops subagent_type", 'SPAWN_RE = re.compile(r"\\b(?:subagent_type|agentType|SendMessage)', 'SPAWN_RE = re.compile(r"\\b(?:agentType|SendMessage)'),
 ("L17 gate drops SendMessage", '(?:subagent_type|agentType|SendMessage)\\b|', '(?:subagent_type|agentType)\\b|'),
 ("L17a gate drops agent(", '\\b(?:agent|Agent|Task)\\(")', '\\b(?:Agent|Task)\\(")'),
 ("L17c gate drops Agent(", '\\b(?:agent|Agent|Task)\\(")', '\\b(?:agent|Task)\\(")'),
 ("L17d gate drops Task(", '\\b(?:agent|Agent|Task)\\(")', '\\b(?:agent|Agent)\\(")'),
 ("L17e gate group1 loses leading \\b", 'SPAWN_RE = re.compile(r"\\b(?:subagent', 'SPAWN_RE = re.compile(r"(?:subagent'),
 ("L17f gate group1 loses trailing \\b", 'SendMessage)\\b|', 'SendMessage)|'),
 ("L17g gate group2 loses leading \\b", '|\\b(?:agent|Agent|Task)\\(")', '|(?:agent|Agent|Task)\\(")'),
 ("L17h gate group2 drops the paren", '(?:agent|Agent|Task)\\(")', '(?:agent|Agent|Task)")'),
 ("L17i gate group2 IGNORECASE-ish: also 'task('", '(?:agent|Agent|Task)\\(")', '(?:agent|Agent|Task|task)\\(")'),
 ("L18 line number off by one (low)", 'f"line {ln + 1}:', 'f"line {ln}:'),
 ("L19 line number off by one (high)", 'f"line {ln + 1}:', 'f"line {ln + 2}:'),
 ("L20 first hit per file only", "        for m in LAZY_RE.finditer(text):\n", "        for m in list(LAZY_RE.finditer(text))[:1]:\n"),
 ("L21 naive line count (quadratic)", 'ln, last = ln + text.count("\\n", last, m.start()), m.start()', 'ln = text.count("\\n", 0, m.start())'),
 ("L22 scan only agents+skills (not nested)", "    for path, text in texts.items():  # a brief", "    for path, text in {k: v for k, v in texts.items() if k in agents + skills}.items():  # a brief"),
 ("L23 gate per line not per file", "        if not SPAWN_RE.search(text):\n            continue\n", "        text = '\\n'.join(l for l in text.splitlines() if SPAWN_RE.search(l))\n"),
 ("L24 skip agents", "    for path, text in texts.items():  # a brief", "    for path, text in {k: v for k, v in texts.items() if k not in agents}.items():  # a brief"),
 ("L25 rule not run (deleted)", '            report("WARN", path, "lazy-delegation", f"line {ln + 1}: {hit!r}")\n', "            pass\n"),
 ("L26 rule id renamed (message only)", '"lazy-delegation", f"line', '"lazy-brief", f"line'),
 ("L27 hit text not normalised (message only)", "hit = \" \".join(m.group(0).split())", "hit = m.group(0)"),
]
only = sys.argv[1:] 
for name, old, new in M:
    if only and not any(name.startswith(o) for o in only): continue
    assert src.count(old) >= 1, (name, "pattern not found")
    mut = src.replace(old, new, 1)
    assert mut != src, name
    with tempfile.TemporaryDirectory(dir=ROOT.parent) as d:
        d = Path(d)
        for p in ("skills", ".claude", "tests/fixtures", "pyproject.toml"):
            s = ROOT / p
            (shutil.copytree if s.is_dir() else shutil.copy)(s, d / p)
        (d / "tests").mkdir(exist_ok=True)
        shutil.copy(ROOT / "tests/test_lint_harness.py", d / "tests/test_lint_harness.py")
        (d / LINT).write_text(mut)
        r = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests/test_lint_harness.py"], cwd=d, capture_output=True, text=True, timeout=300)
        tail = [l for l in r.stdout.splitlines() if l.startswith(("FAILED", "ERROR")) or " passed" in l or " failed" in l]
        print(f"{name:45} {'KILLED' if r.returncode else 'SURVIVED'}  {tail[-1][:90] if tail else ''}")
