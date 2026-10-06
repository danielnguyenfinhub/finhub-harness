"""QA mutant batch Q01-Q90 (from the QA report, q9x/mut/qamut.py), parametrised. Usage:
Q_TREE=<patched tree> Q_SCRATCH=<dir> Q_PY=<python> python 02_strategy-architect_C9_qa_mutants.py [id-prefix]
Q14-Q16, Q21, Q23, Q25, Q29, Q30 are re-expressed against the rev-3c text; Q17-Q20, Q22, Q24, Q26 mutate code that rev 3c removed (reported N/A).
"""
import difflib, os, shutil, subprocess, sys, tarfile, tempfile, time
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.abspath(os.environ["Q_SCRATCH"]); PY = os.environ.get("Q_PY", "python"); TREE = os.path.abspath(os.environ["Q_TREE"])
G = "src/master_finhub/evals/gates.py"; S = "src/master_finhub/sandbox/stream.py"
def m(i, what, f, old, new, n=1, seeds=False): return dict(id=i, what=what, edits=[(f, old, new, n)], seeds=seeds)
M = [
 m("Q01","_base keeps case (no lower)",G,'name = word.rsplit("/", 1)[-1].lower()','name = word.rsplit("/", 1)[-1]'),
 m("Q02","_base .exe suffix upper-case (never matches after lower)",G,'removesuffix(".exe")','removesuffix(".EXE")'),
 m("Q03","_base takes first path segment",G,'word.rsplit("/", 1)[-1].lower()','word.split("/")[0].lower()'),
 m("Q04","SHELL_NAMES drop rbash",G,'        "rbash",\n',''),
 m("Q05","SHELL_NAMES drop yash",G,'        "yash",\n',''),
 m("Q06","SHELL_NAMES drop posh",G,'        "posh",\n',''),
 m("Q07","SHELL_NAMES drop csh",G,'        "csh",\n',''),
 m("Q08","names set starts empty (resolved name only)",G,'    names = {first}\n','    names = set()\n'),
 m("Q09","resolved path added whole not basename",G,'names.add(_base(found))','names.add(found)'),
 m("Q10","watch no longer refused",G,'SHELL_RUNNERS: Final = frozenset({"su", "watch"})','SHELL_RUNNERS: Final = frozenset({"su"})'),
 m("Q11","su no longer refused",G,'SHELL_RUNNERS: Final = frozenset({"su", "watch"})','SHELL_RUNNERS: Final = frozenset({"watch"})'),
 m("Q12","PATH candidate: drop X_OK test",G,'if os.path.isfile(candidate) and os.access(candidate, os.X_OK):','if os.path.isfile(candidate):'),
 m("Q13","PATH candidate: drop isfile test",G,'if os.path.isfile(candidate) and os.access(candidate, os.X_OK):','if os.access(candidate, os.X_OK):'),
 m("Q14","PATH entries not joined onto the gate cwd",G,'base = _walk(os.path.join(cwd, entry))','base = _walk(entry)'),
 m("Q15","slash test only for absolute words",G,'if "/" in word:\n        return _walk','if word.startswith("/"):\n        return _walk'),
 m("Q16","relative path joined onto runner cwd",G,'return _walk(os.path.join(cwd, word))','return _walk(os.path.join(os.getcwd(), word))'),
# Q17: N/A in rev 3c, the code it mutated (normpath, final realpath check, link-walk helper) no longer exists; covered by W01-W16, V-series
 # m("Q17","final real = abspath (no symlink resolution)",G,'real = os.path.realpath(path)','real = os.path.abspath(path)'),
# Q18: N/A in rev 3c, the code it mutated (normpath, final realpath check, link-walk helper) no longer exists; covered by W01-W16, V-series
 # m("Q18","final realpath opaque check dropped",G,'    real = os.path.realpath(path)\n    if _opaque(real):\n        raise _Opaque\n','    real = os.path.realpath(path)\n'),
# Q19: N/A in rev 3c, the code it mutated (normpath, final realpath check, link-walk helper) no longer exists; covered by W01-W16, V-series
 # m("Q19","link walk dropped from _checked_real",G,'if _opaque(path) or _link_into_opaque(path):','if _opaque(path):'),
# Q20: N/A in rev 3c, the code it mutated (normpath, final realpath check, link-walk helper) no longer exists; covered by W01-W16, V-series
 # m("Q20","link loop fails open",G,'    if hops > 40:\n        return True','    if hops > 40:\n        return False'),
 m("Q21","link limit 1",G,'if links > 40:','if links > 1:'),
# Q22: N/A in rev 3c, the code it mutated (normpath, final realpath check, link-walk helper) no longer exists; covered by W01-W16, V-series
 # m("Q22","only last-component links walked",G,'        if os.path.islink(cur):','        if os.path.islink(cur) and i == len(parts) - 1:'),
 m("Q23","link target not pushed onto the walk",G,'todo.extend(target.split("/")[::-1])','pass'),
# Q24: N/A in rev 3c, the code it mutated (normpath, final realpath check, link-walk helper) no longer exists; covered by W01-W16, V-series
 # m("Q24","no recursion into link target",G,'return _opaque(nxt) or _link_into_opaque(nxt, hops + 1)','return _opaque(nxt)'),
 m("Q25","_opaque prefix without slash",G,'path.startswith(root + "/")','path.startswith(root)'),
# Q26: N/A in rev 3c, the code it mutated (normpath, final realpath check, link-walk helper) no longer exists; covered by W01-W16, V-series
 # m("Q26","_opaque keeps double leading slash",G,'p = "/" + os.path.normpath(path).lstrip("/")','p = os.path.normpath(path)'),
 m("Q27","OPAQUE_ROOTS drop /dev",G,'OPAQUE_ROOTS: Final = ("/proc", "/dev")','OPAQUE_ROOTS: Final = ("/proc",)'),
 m("Q28","OPAQUE_ROOTS drop /proc",G,'OPAQUE_ROOTS: Final = ("/proc", "/dev")','OPAQUE_ROOTS: Final = ("/dev",)'),
 m("Q29","_Refused in _shell_refusal swallowed",G,'    except _Refused as exc:\n        return str(exc)\n','    except _Refused:\n        pass\n'),
 m("Q30","PATH entry not walked (no /proc check on it)",G,'base = _walk(os.path.join(cwd, entry))','base = os.path.join(cwd, entry)'),
 m("Q31","WRAPPERS drop env",G,'{"env", "xargs",','{"xargs",'),
 m("Q32","wrapper rule looks only at argv[1]",G,'any(_base(a) in SHELL_NAMES for a in argv[1:])','_base(argv[1]) in SHELL_NAMES if len(argv) > 1 else False'),
 m("Q33","wrapper rule skips first later argument",G,'for a in argv[1:])','for a in argv[2:])'),
 m("Q34","wrapper rule: or instead of and",G,'if first in WRAPPERS and any(','if first in WRAPPERS or any('),
 m("Q35","WRAPPERS drop find",G,'"nice", "ionice", "setsid", "stdbuf", "chroot", "find", "flock",','"nice", "ionice", "setsid", "stdbuf", "chroot", "flock",'),
 m("Q36","WRAPPERS drop timeout",G,'"sudo", "doas", "timeout",','"sudo", "doas",'),
 m("Q37","shell+argv accepted",G,'if shell and command is None:','if shell and argv is None:'),
 m("Q38","shell type check dropped",G,'    if not isinstance(shell, bool):\n        raise _bad(f"gate {n}: shell must be true or false")\n','    if False:\n        raise _bad(f"gate {n}: shell must be true or false")\n'),
 m("Q39","--allow-shell check dropped",G,'            if not allow_shell:\n                return "shell gate refused: pass --allow-shell"\n','            if False:\n                return "shell gate refused: pass --allow-shell"\n'),
 m("Q40","metachar \\r dropped",G,'SHELL_METACHARS: Final = frozenset(";&|`$<>\\n\\r")','SHELL_METACHARS: Final = frozenset(";&|`$<>\\n")'),
 m("Q41","metachar backtick dropped",G,'SHELL_METACHARS: Final = frozenset(";&|`$<>\\n\\r")','SHELL_METACHARS: Final = frozenset(";&|$<>\\n\\r")'),
 m("Q42","metachar scan skips first char",G,'for ch in text)','for ch in text[1:])'),
 m("Q43","string split without shlex",G,'return tuple(shlex.split(text))','return tuple(text.split())'),
 m("Q44","shlex non-posix",G,'return tuple(shlex.split(text))','return tuple(shlex.split(text, posix=False))'),
 m("Q45","text cap off by one",G,'if len(text) > MAX_TEXT_CHARS:\n        return "command is too long"\n    if any(ch','if len(text) >= MAX_TEXT_CHARS:\n        return "command is too long"\n    if any(ch'),
 m("Q46","spawn env unscrubbed",G,'env=scrubbed_env()','env=dict(os.environ)'),
 m("Q47","spawn cwd dropped",G,'cwd=str(plan.cwd))','cwd=None)'),
 m("Q48","spawn ignores remaining total budget",G,'timeout_s=timeout_s, cwd','timeout_s=gate.timeout_s, cwd'),
 m("Q49","SIGTERM(-15) treated as pass",G,'    if res.exit_code == 0:\n        return done("pass"','    if res.exit_code in (0, -15):\n        return done("pass"'),
 m("Q50","timeout only when exit code non-zero",G,'    if res.timed_out:\n','    if res.timed_out and res.exit_code != 0:\n'),
 m("Q51","missing exit status passes",G,'return done("error", None, "no exit status", out, err, cut)','return done("pass", 0, "", out, err, cut)'),
 m("Q52","one ready gate is spawned despite a refusal",G,'if len(ready) != len(plans):','if not ready:'),
 m("Q53","total budget ignores total_s",G,'deadline = time.monotonic() + total_s','deadline = time.monotonic() + MAX_TOTAL_S'),
 m("Q54","duplicate id check dropped",G,'if len({g.id for g in gates}) != len(gates):','if False:'),
 m("Q55","empty gates list accepted at load",G,'if not isinstance(rows, list) or not rows:','if not isinstance(rows, list):'),
 m("Q56","gate count cap >= instead of >",G,'if len(rows) > MAX_GATES:','if len(rows) >= MAX_GATES:'),
 m("Q57","schema_version bool/float accepted",G,'if type(version) is not int or version != SCHEMA_VERSION:','if version != SCHEMA_VERSION:'),
 m("Q58","unknown gate key accepted",G,'if not set(entry) <= GATE_KEYS:','if False:'),
 m("Q59","id ascii check dropped",G,'        and value.isascii()\n',''),
 m("Q60","id length 65 allowed",G,'0 < len(value) <= 64','0 < len(value) <= 65'),
 m("Q61","duplicate JSON keys accepted",G,'    if len(out) != len(pairs):\n        raise ValueError("duplicate JSON key")\n','    if False:\n        raise ValueError("duplicate JSON key")\n'),
 m("Q62","loader uses exists (FIFO would block)",G,'if not os.path.isfile(path):','if not os.path.exists(path):'),
 m("Q63","file read cap exact (not +1)",G,'fh.read(MAX_FILE_BYTES + 1)','fh.read(MAX_FILE_BYTES)'),
 m("Q64","timeout lower bound dropped",G,'return seconds if 0 < seconds <= MAX_TIMEOUT_S else None','return seconds if seconds <= MAX_TIMEOUT_S else None'),
 m("Q65","timeout bool accepted",G,'if isinstance(value, bool) or not isinstance(value, (int, float)):','if not isinstance(value, (int, float)):'),
 m("Q66","exit code policy-error -> 1",G,'return 2 if any(r.status == "policy-error" for r in report.gates) else 1','return 1'),
 m("Q67","SIGHUP not handled",G,'HANDLED_SIGNALS: Final = (signal.SIGTERM, signal.SIGHUP)','HANDLED_SIGNALS: Final = (signal.SIGTERM,)'),
 m("Q68","signal exit status 0",G,'raise SystemExit(128 + signum)','raise SystemExit(0)'),
 m("Q69","handlers restored to SIG_DFL always",G,'signal.signal(old_sig, signal.SIG_DFL if previous is None else previous)','signal.signal(old_sig, signal.SIG_DFL)'),
 m("Q70","stream.py cwd keyword ignored",S,'        cwd=cwd,\n','        cwd=None,\n'),
 m("Q71","argv[0] dash check dropped",G,'    if argv[0].startswith("-"):\n        return "the executable starts with \'-\'"\n',''),
 m("Q72","argv[0] equals check dropped",G,'    if "=" in argv[0]:\n        return "the executable contains \'=\' (environment prefixes need shell: true)"\n',''),
 m("Q73","NUL check only argv[0]",G,'if any("\\x00" in a for a in argv):','if "\\x00" in argv[0]:'),
 m("Q74","argv count cap off by one",G,'if len(argv) > MAX_ARGV_ITEMS or','if len(argv) > MAX_ARGV_ITEMS + 1 or'),
 m("Q75","gate cwd fence dropped",G,'cwd = ws.check_read(gate.cwd)','cwd = Path(gate.cwd)'),
 m("Q76","cwd is_dir check dropped",G,'        if not cwd.is_dir():\n            return "cwd is not a folder"\n',''),
 m("Q77","shell refusal for shell gates instead of non-shell",G,'if not gate.shell:  # needs the gate','if gate.shell:  # needs the gate'),
 m("Q78","guard denial ignored",G,'        if denial is not None:\n            return denial\n',''),
 m("Q79","guard sees only the executable",G,'line = shlex.join(argv)','line = argv[0]'),
 m("Q80","tail not redacted",G,'cleaned = redact_secrets(text)[0]','cleaned = text'),
 m("Q81","tail keeps the start",G,'return cleaned[-TAIL_CHARS:], len(cleaned) > TAIL_CHARS','return cleaned[:TAIL_CHARS], len(cleaned) > TAIL_CHARS'),
 m("Q82","truncated flag ignores capture window",G,'cut = res.truncated or cut_out or cut_err','cut = cut_out or cut_err'),
 m("Q83","shell refusal resolved from runner cwd",G,'refusal = _shell_refusal(argv, cwd)','refusal = _shell_refusal(argv, Path.cwd())'),
 m("Q84","gates parsed through a set (hash-seed order)",G,'gates = tuple(_parse_gate(i, row) for i, row in enumerate(rows, 1))','gates = tuple(set(_parse_gate(i, row) for i, row in enumerate(rows, 1)))',1,True),
 m("Q85","plans reversed at run time",G,'    for g, p in zip(gates, ready, strict=True):\n','    for g, p in reversed(list(zip(gates, ready, strict=True))):\n'),
 m("Q86","exit 0 when only some passed (>=1)",G,'return GateReport(tuple(results), passed, total - passed, total, total > 0 and passed == total)','return GateReport(tuple(results), passed, total - passed, total, passed > 0)'),
 m("Q87","spawn failure reported pass",G,'return done("error", None, f"could not start ({type(exc).__name__})")','return done("pass", 0, "")'),
 m("Q88","report lost -> exit code 1",G,'return code if _emit(json.dumps(out, indent=2)) else _stdout_lost()','return code if _emit(json.dumps(out, indent=2)) else 1'),
 m("Q89","shell runs via sh not /bin/sh abs path",G,'SHELL_PATH: Final = "/bin/sh"','SHELL_PATH: Final = "sh"'),
 m("Q90","shell gate argv without -c",G,'argv: tuple[str, ...] = (SHELL_PATH, "-c", raw)','argv: tuple[str, ...] = (SHELL_PATH, "-c", raw.strip())'),
]
TIMING = set()
def apply(root, edits):
    for f, old, new, n in edits:
        p = os.path.join(root, f); s = open(p, encoding="utf-8").read()
        if s.count(old) != n: raise RuntimeError(f"{f}: expected {n} occurrences, found {s.count(old)}: {old[:60]!r}")
        open(p, "w", encoding="utf-8").write(s.replace(old, new))
def one(mut, serial=False):
    work = tempfile.mkdtemp(prefix="m_", dir=os.path.join(HERE, "w")); 
    with tarfile.open(os.path.join(HERE, "base.tar")) as t: t.extractall(work)
    ref = tempfile.mkdtemp(prefix="r_", dir=os.path.join(HERE, "w"))
    with tarfile.open(os.path.join(HERE, "base.tar")) as t: t.extractall(ref)
    try: apply(work, mut["edits"])
    except RuntimeError as e: return mut["id"], "ERROR", str(e), ""
    diff = "".join(difflib.unified_diff(open(os.path.join(ref, mut["edits"][0][0])).read().splitlines(1), open(os.path.join(work, mut["edits"][0][0])).read().splitlines(1), n=0))
    if not diff.strip(): return mut["id"], "ERROR", "empty diff (no-op)", ""
    env = dict(os.environ, PYTHONPATH=work + "/src", PYTHONDONTWRITEBYTECODE="1")
    chk = subprocess.run([PY, "-B", "-c", "import master_finhub.evals.gates as g;print(g.__file__)"], env=env, cwd=work, capture_output=True, text=True).stdout.strip()
    if not chk.startswith(work): return mut["id"], "ERROR", "module path not the copy: " + chk, ""
    seeds = range(40) if mut["seeds"] else [None]
    res = "SURVIVED"; first = ""
    for sd in seeds:
        e = dict(env); 
        if sd is not None: e["PYTHONHASHSEED"] = str(sd)
        try:
            p = subprocess.run([PY, "-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "tests/test_gates.py"], env=e, cwd=work, capture_output=True, text=True, timeout=240)
            rc, out = p.returncode, p.stdout
        except subprocess.TimeoutExpired: rc, out = 124, "TIMEOUT"
        if rc != 0:
            fl = [l for l in out.splitlines() if l.startswith("FAILED") or "TIMEOUT" in l]
            res = "KILLED" if sd is None else "KILLED"; first = (fl[0][:140] if fl else out[-120:])
            if sd is None: break
            continue
        else:
            res = "SURVIVED" if sd is None else "SURVIVED(seed %d)" % sd; first = ""; break
    shutil.rmtree(work, ignore_errors=True); shutil.rmtree(ref, ignore_errors=True)
    return mut["id"], res, first, diff
if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "w"), exist_ok=True)
    with tarfile.open(os.path.join(HERE, "base.tar"), "w") as t:
        for item in ("src", "tests", "pyproject.toml", ".gitignore"):
            t.add(os.path.join(TREE, item), arcname=item, filter=lambda ti: None if "__pycache__" in ti.name else ti)
    only = sys.argv[1:] 
    sel = [x for x in M if not only or any(x["id"].startswith(o) for o in only)]
    jobs = int(os.environ.get("QJOBS", "4")); t0 = time.time()
    with ThreadPoolExecutor(jobs) as ex: out = list(ex.map(one, sel))
    for i, r, f, d in out: print(f"{i} {r} {f}")
    print("TOTAL", len(out), "killed", sum(r == "KILLED" for _, r, _, _ in out), "survived", [i for i, r, _, _ in out if r.startswith("SURV")], "errors", [(i, f) for i, r, f, _ in out if r == "ERROR"], round(time.time() - t0))
