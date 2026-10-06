"""The judge's round-3 mutants K01-K15 (verdict round 3, j9r3/r3mut.py), parametrised. Usage:
J_TREE=<patched tree> J_SCRATCH=<dir> J_PY=<python> python 02_strategy-architect_C9_judge_r3_mutants.py
K01-K04, K09, K10 are re-expressed against the rev-3c text (one physical walk, `_walk`; K09: the hit is walked BEFORE the file test, so the mutant returns it unwalked); same intent. Each edit must occur exactly once.
"""
import os, sys, shutil, subprocess, tempfile, difflib
from pathlib import Path
PAT = Path(os.environ["J_TREE"]).resolve(); PY = os.environ.get("J_PY", "python")
G = "src/master_finhub/evals/gates.py"
M = [
 ("K01","slash word resolved from runner cwd (realpath(word))", G, '        return _walk(os.path.join(cwd, word))\n', '        return _walk(word)\n'),
 ("K02","slash word joined onto os.getcwd()", G, '        return _walk(os.path.join(cwd, word))\n', '        return _walk(os.path.join(os.getcwd(), word))\n'),
 ("K03","PATH entry not anchored on the gate cwd", G, '        base = _walk(os.path.join(cwd, entry))\n', '        base = _walk(entry)\n'),
 ("K04","PATH entry anchored on runner cwd", G, '        base = _walk(os.path.join(cwd, entry))\n', '        base = _walk(os.path.join(os.getcwd(), entry))\n'),
 ("K05","no executable test on the PATH hit", G, 'if os.path.isfile(candidate) and os.access(candidate, os.X_OK):', 'if os.path.isfile(candidate):'),
 ("K06","exists instead of isfile (directory counts)", G, 'if os.path.isfile(candidate) and os.access(candidate, os.X_OK):', 'if os.path.exists(candidate) and os.access(candidate, os.X_OK):'),
 ("K07","relative PATH entries ignored", G, 'for entry in os.get_exec_path():', 'for entry in [e for e in os.get_exec_path() if os.path.isabs(e)]:'),
 ("K08","last PATH hit instead of first", G, 'for entry in os.get_exec_path():', 'for entry in reversed(os.get_exec_path()):'),
 ("K09","PATH hit not realpath-ed (rev 3c text: the hit is returned unwalked)", G, '            return candidate\n', '            return os.path.join(base, word)\n'),
 ("K10","path word not realpath-ed (abspath)", G, '        return _walk(os.path.join(cwd, word))\n', '        return os.path.abspath(os.path.join(cwd, word))\n'),
 ("K11","default PATH instead of the process PATH", G, 'for entry in os.get_exec_path():', 'for entry in os.defpath.split(":"):'),
 ("K12","resolved name never added", G, '            names.add(_base(found))\n', '            pass\n'),
 ("K13","shell check runs on cwd=Path.cwd() (fence order irrelevant)", G, 'refusal = _shell_refusal(argv, cwd)', 'refusal = _shell_refusal(argv, Path.cwd())'),
 ("K14","shell check skipped when the cwd is not the root", G, 'if not gate.shell:  # needs', 'if not gate.shell and gate.cwd in (".", ""):  # needs'),
 ("K15","empty PATH entry skipped", G, 'for entry in os.get_exec_path():', 'for entry in [e for e in os.get_exec_path() if e]:'),
]
def run(mid, what, f, old, new):
    d = Path(tempfile.mkdtemp(prefix="k_", dir=os.environ['J_SCRATCH']))
    for item in ("src","tests","pyproject.toml",".gitignore"):
        s = PAT/item
        if s.is_dir(): shutil.copytree(s, d/item, ignore=shutil.ignore_patterns("__pycache__"), symlinks=True)
        else: shutil.copy(s, d/item)
    p = d/f; t = p.read_text()
    assert t.count(old) == 1, (mid, t.count(old))
    p.write_text(t.replace(old, new))
    env = dict(os.environ); env.pop("PYTHONPATH", None)
    r = subprocess.run([PY, "-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests/test_gates.py"], cwd=d, env=env, capture_output=True, text=True)
    tail = [l for l in r.stdout.splitlines() if l.startswith("FAILED") or " passed" in l or " failed" in l]
    shutil.rmtree(d, ignore_errors=True)
    return mid, ("KILLED" if r.returncode else "SURVIVED"), what, (tail[0][:170] if tail else r.stdout[-200:])
res = [run(*m) for m in M]
for r in res: print(*r)
print('TOTAL', len(res), 'killed', sum(r[1] == 'KILLED' for r in res), 'survived', [r[0] for r in res if r[1] == 'SURVIVED'])
