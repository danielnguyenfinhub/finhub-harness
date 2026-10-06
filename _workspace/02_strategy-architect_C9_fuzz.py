"""C9 differential fuzz: the kernel's resolution of the executable word versus the plan.
Usage: python 02_strategy-architect_C9_fuzz.py <tree> <seed> <layouts>   (the tree holds src/master_finhub)

Per layout: a fresh folder B with bin/bash (a test-made shell that creates MARK), sub/, a/b/, x/y/ and
up to 10 symlinks (ingredients: /proc/self/cwd, /proc/thread-self/cwd, /proc/self/root<B>/sub, `..` chains,
absolute and relative targets, `lnk/../mysh`), then 40 random words (prefixes //, ./, /proc/self/cwd/, ../,
random parts; bare names with a random PATH).  Truth: THIS process with its cwd set to B/sub stats the
word (what the child's exec resolves; /proc/self/cwd is then B/sub; the PATH search takes the first
executable regular file).  Plan: gates._shell_refusal with the process cwd in B/a/b (the runner).
VIOLATION = the kernel reaches the test-made bash and the plan accepts.  The line `model-vs-real-exec`
spawns the same word with Popen(cwd=B/sub) for every route to the shell and a 1% sample of the rest and
counts (model says reached, real run made MARK): the two must agree.  Exit 1 on any violation.
"""
import subprocess, os, random, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, sys.argv[1] + "/src")
import master_finhub.evals.gates as gm
SEED = int(sys.argv[2]); N = int(sys.argv[3])
rnd = random.Random(SEED)
FAKE = "#!/bin/sh\n: > MARK\n"
NAMES = ["l1", "l2", "l3", "mysh", "d", "e"]
TOK = NAMES + ["lnk", "up", "mysh2", "z", "m3", "q", "..", "..", ".", "sub", "bin", "bash", "x", "y", "", "proc", "self", "cwd", "root", "dev", "fd"]
def toks(k): return [rnd.choice(TOK) for _ in range(k)]
def target(B, bash):
    r = rnd.random()
    if r < 0.12: return rnd.choice(["/proc/self/cwd", "/proc/thread-self/cwd", "/proc/self/root", "/dev", "/dev/fd", "/proc/self/exe", "/dev/stdin", "/proc/self", "/proc"]) + ("/" + "/".join(toks(rnd.randint(0, 3))) if rnd.random() < .6 else "")
    if r < 0.3: return B + "/" + "/".join(toks(rnd.randint(1, 4)))
    if r < 0.45: return "../" * rnd.randint(1, 14) + "/".join(toks(rnd.randint(0, 3)))
    if r < 0.6: return rnd.choice(["bin/bash", "../bin/bash", bash, "../../bin/bash", "./bash", "bash"])
    return "/".join(toks(rnd.randint(1, 4)))
def samebash(w, bash_st):
    try:
        st = os.stat(w)
    except OSError:
        return False
    return (st.st_dev, st.st_ino) == bash_st
xcheck = {}
viol = ran = over = tot = 0
seen = set()
for it in range(N):
    B = Path(tempfile.mkdtemp(prefix="fz_")).resolve()
    try:
        for d in ["bin", "sub", "a/b", "x/y"]:
            (B / d).mkdir(parents=True)
        bash = B / "bin/bash"; bash.write_text(FAKE); bash.chmod(0o755)
        bst = os.stat(bash); bst = (bst.st_dev, bst.st_ino)
        dirs = [B, B / "sub", B / "bin", B / "x", B / "x/y"]
        desc = []
        ING = [("sub/lnk", rnd.choice(["/proc/self/cwd", "/proc/thread-self/cwd", "/proc/self/root" + str(B) + "/sub", "../" * 12 + "proc/self/cwd", ".", "/proc/self/cwd/.", "/proc/self/cwd/../sub"])),
               ("sub/up", rnd.choice(["..", "../", "../.", "../sub/..", "../x/.."])),
               ("sub/d", rnd.choice(["../bin", str(B / "bin"), "../x/../bin", "up/bin"])),
               ("mysh", rnd.choice(["bin/bash", "./bin/bash", str(B / "bin/bash")])),
               ("sub/mysh2", rnd.choice(["../bin/bash", "d/bash", "../mysh", "lnk/../mysh"])),
               ("x/y/z", rnd.choice(["../../bin", "../../mysh", "../../sub/lnk", "../../sub/up"])),
               ("bin/m3", rnd.choice(["bash", "./bash", "../mysh", "../sub/mysh2"])),
               ("x/q", rnd.choice(["y/z", "y/z/bash", "../mysh"]))]
        for p, tg in ING:
            if rnd.random() < .8:
                os.symlink(tg, B / p); desc.append((p, tg))
        for _ in range(rnd.randint(0, 2)):
            p = rnd.choice(dirs) / rnd.choice(NAMES)
            if os.path.lexists(p): continue
            t = target(str(B), str(bash)) or "bin/bash"
            os.symlink(t, p); desc.append((str(p.relative_to(B)), t))
        for _ in range(40):
            if rnd.random() < .25:
                word = rnd.choice(NAMES + ["bash", "mysh", "mysh2", "m3", "lnk"]); path = ":".join(rnd.choice(["", ".", "sub", "bin", "x", str(B / "sub"), str(B / "x/y"), str(B / "bin"), "/proc/self/cwd", "d", "e", "l1", "l2"]) for _ in range(rnd.randint(1, 3)))
            else:
                pre = rnd.choice(["", "./", str(B) + "/", "/proc/self/cwd/", "sub/", "../", "/", "//", "bin/", str(B / "sub") + "/"])
                word = pre + "/".join(toks(rnd.randint(0, 4)) + [rnd.choice(NAMES + ["bash", "mysh", "mysh2", "m3", "z", "q"])]); path = None
            if not word or word.startswith("-") or "=" in word or word.endswith("/"): continue
            if "/" not in word and path is None: path = os.environ["PATH"]
            # truth: process cwd == gate cwd
            os.chdir(B / "sub")
            if path is None:
                reached = samebash(word, bst)
            else:
                reached = False
                for e in path.split(":"):
                    c = os.path.join(e, word)
                    if os.path.isfile(c) and os.access(c, os.X_OK):
                        reached = samebash(c, bst); break
            os.chdir(B / "a/b")
            if reached or rnd.random() < .01:
                envp = dict(os.environ)
                if path is not None: envp["PATH"] = path
                for m in B.rglob("MARK"): m.unlink()
                try: subprocess.run([word], cwd=B / "sub", env=envp, stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
                except Exception: pass
                real = any(True for _ in B.rglob("MARK"))
                xcheck[(reached, real)] = xcheck.get((reached, real), 0) + 1
            old = os.environ.get("PATH")
            if path is not None: os.environ["PATH"] = path
            try:
                got = gm._shell_refusal((word,), B / "sub")
            finally:
                if old is None: os.environ.pop("PATH", None)
                else: os.environ["PATH"] = old
            tot += 1
            if reached:
                ran += 1
                if got is None:
                    viol += 1; print("VIOLATION", repr(word), "PATH=", path, desc, flush=True)
            elif got is not None and "shell" not in got and "' '" not in got:
                over += 1
    finally:
        os.chdir("/")
        shutil.rmtree(B, ignore_errors=True)
print("model-vs-real-exec", xcheck); print("seed", SEED, "layouts", N, "words", tot, "truth-reaches-bash", ran, "VIOLATIONS", viol, "non-shell refusals (cost)", over)
sys.exit(1 if viol else 0)
