"""Judge round-2 independent mutants J01-J48 (verdict round 2, j9r2/mut/r2mut.py), parametrised. Usage:
J_TREE=<patched tree> J_SCRATCH=<dir> J_PY=<python> [J_JOBS=n] python r2mut.py [ids]Re-expressed for rev 3 (the resolution moved into _resolve, the shell check moved after the cwd fence): J08-J11, J19-J21.
"""
import os, sys, shutil, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
PAT = os.path.abspath(os.environ["J_TREE"]); PY = os.environ.get("J_PY", "python"); SCR = os.path.abspath(os.environ["J_SCRATCH"])
JOBS = int(os.environ.get("J_JOBS", "3"))
G = "src/master_finhub/evals/gates.py"; T = "tests/test_gates.py"
SH = 'if names & SHELL_NAMES or first in SHELL_RUNNERS:'
M = [
("J01", "su/watch refusal removed", G, SH, 'if names & SHELL_NAMES:'),
("J02", "SHELL_RUNNERS loses watch", G, 'frozenset({"su", "watch"})', 'frozenset({"su"})'),
("J03", "SHELL_RUNNERS loses su", G, 'frozenset({"su", "watch"})', 'frozenset({"watch"})'),
("J04", "no lower-casing in _base", G, 'rsplit("/", 1)[-1].lower()', 'rsplit("/", 1)[-1]'),
("J05", ".exe not stripped", G, '    return name.removesuffix(".exe")', '    return name'),
("J06", "wrong suffix stripped", G, 'removesuffix(".exe")', 'removesuffix("exe")'),
("J07", "no basename (whole word)", G, 'name = word.rsplit("/", 1)[-1].lower()', 'name = word.lower()'),
("J08", "resolution result not used (rev 3c text: the hit is returned unwalked)", G, '            return candidate\n', '            return os.path.join(base, word)\n'),
("J09", "PATH lookup dropped (rev 3 text)", G, '    for entry in os.get_exec_path():\n', '    for entry in ():\n'),
("J10", "PATH lookup limited to /bin (rev 3 text)", G, '    for entry in os.get_exec_path():\n', '    for entry in ("/bin",):\n'),
("J11", "slash test on backslash (rev 3 text)", G, '    if "/" in word:\n', '    if "\\\\" in word:\n'),
("J12", "resolution result ignored (names = literal only)", G, 'if names & SHELL_NAMES or first in SHELL_RUNNERS:', 'if first in SHELL_NAMES or first in SHELL_RUNNERS:'),
("J13", "wrapper rule skips the first later arg", G, 'for a in argv[1:])', 'for a in argv[2:])'),
("J14", "wrapper rule scans argv incl. argv[0] (maybe equivalent)", G, 'for a in argv[1:])', 'for a in argv)'),
("J15", "wrapper rule: and -> or", G, 'if first in WRAPPERS and any(', 'if first in WRAPPERS or any('),
("J16", "wrapper later-arg compared without basename", G, 'any(_base(a) in SHELL_NAMES for a in argv[1:])', 'any(a in SHELL_NAMES for a in argv[1:])'),
("J17", "wrapper name compared case-sensitively with raw argv[0]", G, 'if first in WRAPPERS and', 'if argv[0] in WRAPPERS and'),
("J18", "wrapper rule dropped", G, 'if first in WRAPPERS and any(_base(a) in SHELL_NAMES for a in argv[1:]):', 'if False:'),
("J19", "shell check also on declared shell gates", G, 'if not gate.shell:  # needs', 'if True:  # needs'),
("J20", "shell check only on declared shell gates", G, 'if not gate.shell:  # needs', 'if gate.shell:  # needs'),
("J21", "shell check dropped entirely", G, 'if not gate.shell:  # needs', 'if False:  # needs'),
("J22", "wrapper message reuses the shell message (maybe equivalent)", G, '"a wrapper is given a shell; declare shell: true and pass --allow-shell"', '"the executable is a shell; declare shell: true and pass --allow-shell"'),
("J23", "OSError while resolving accepted (rev 3c text: fail open instead of a refusal)", G, '        return "the executable path could not be examined"\n', '        pass\n'),
("J24", "SHELL_NAMES loses ash", G, '        "ash",\n', ''),
("J25", "SHELL_NAMES loses fish", G, '        "fish",\n', ''),
("J26", "SHELL_NAMES loses rbash", G, '        "rbash",\n', ''),
("J27", "SHELL_NAMES loses tcsh", G, '        "tcsh",\n', ''),
("J28", "SHELL_NAMES loses posh", G, '        "posh",\n', ''),
("J29", "SHELL_NAMES loses yash", G, '        "yash",\n', ''),
("J30", "SHELL_NAMES loses sh", G, '        "sh",\n', ''),
("J31", "WRAPPERS loses timeout", G, ' "doas", "timeout",\n', ' "doas",\n'),
("J32", "WRAPPERS loses xargs", G, '"env", "xargs", "busybox"', '"env", "busybox"'),
("J33", "WRAPPERS loses find", G, '"stdbuf", "chroot", "find", "flock"', '"stdbuf", "chroot", "flock"'),
("J34", "WRAPPERS loses env", G, '{"env", "xargs"', '{"xargs"'),
("J35", "WRAPPERS gains pytest", G, '{"env", "xargs"', '{"pytest", "env", "xargs"'),
("J36", "WRAPPERS gains python", G, '{"env", "xargs"', '{"python", "env", "xargs"'),
("J37", "WRAPPERS loses parallel", G, ', "ssh", "parallel"}', ', "ssh"}'),
("J38", "SIGHUP not handled", G, 'HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGHUP)', 'HANDLED_SIGNALS: Final = (signal.SIGTERM,)'),
("J39", "SIGTERM not handled", G, 'HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGHUP)', 'HANDLED_SIGNALS: Final = (signal.SIGHUP,)'),
("J40", "handler order swapped (maybe equivalent)", G, '(signal.SIGTERM, signal.SIGHUP)', '(signal.SIGHUP, signal.SIGTERM)'),
("J41", "exit code is the signal number", G, 'raise SystemExit(128 + signum)', 'raise SystemExit(signum)'),
("J42", "exit code fixed 143", G, 'raise SystemExit(128 + signum)', 'raise SystemExit(143)'),
("J43", "off-main-thread guard removed", G, 'except ValueError:  # not the main thread: leave the handlers alone', 'except ZeroDivisionError:  # not the main thread: leave the handlers alone'),
("J44", "only the first handler restored", G, 'for old_sig, previous in saved:', 'for old_sig, previous in saved[:1]:'),
("J45", "handlers never installed", G, 'with _signals_raise():', 'with contextlib.nullcontext():'),
("J46", "restore None falls back to SIG_IGN", G, 'signal.SIG_DFL if previous is None else previous', 'signal.SIG_IGN if previous is None else previous'),
("J47", "handlers restored before the run finishes (inside try)", G, '    try:\n        yield\n    finally:\n        for old_sig', '    try:\n        pass\n    finally:\n        yield\n        for old_sig'),
("J48", "restore only when not None", G, 'signal.signal(old_sig, signal.SIG_DFL if previous is None else previous)', 'None if previous is None else signal.signal(old_sig, previous)'),
]
def run(m):
    i, what, f, old, new = m
    src = open(os.path.join(PAT, f), encoding="utf-8").read()
    n = src.count(old)
    if n != 1: return (i, what, "BADMUT count=%d" % n, "")
    d = tempfile.mkdtemp(prefix="jm_", dir=SCR); t = os.path.join(d, "t")
    shutil.copytree(PAT, t, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__", "dist", "references", "_workspace"))
    open(os.path.join(t, f), "w", encoding="utf-8").write(src.replace(old, new))
    assert open(os.path.join(t, f), encoding="utf-8").read() != src
    env = dict(os.environ); env.pop("PYTHONPATH", None)
    try:
        r = subprocess.run([PY, "-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", T], cwd=t, env=env, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return (i, what, "KILLED(timeout)", "")
    lines = r.stdout.strip().splitlines(); fl = [l for l in lines if l.startswith("FAILED")]
    st = "SURVIVED" if r.returncode == 0 else "KILLED"
    shutil.rmtree(d, ignore_errors=True)
    return (i, what, st, fl[0][:160] if fl else (lines[-1] if lines else ""))
if __name__ == "__main__":
    only = sys.argv[1:]
    ms = [m for m in M if not only or m[0] in only]
    with ThreadPoolExecutor(JOBS) as ex: res = list(ex.map(run, ms))
    for r in res: print(*r, sep=" | ")
    print("TOTAL", len(res), "killed", sum(r[2].startswith("KILLED") for r in res), "survived", [r[0] for r in res if r[2] == "SURVIVED"], "bad", [r[0] for r in res if r[2].startswith("BAD")])
