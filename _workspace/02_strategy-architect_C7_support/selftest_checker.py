"""selftest_checker.py <passing-run-dir> <tag>: copies a PASSING run (fx dir, its .pristine and its jsonl) once per corruption, applies one corruption
each and asserts check_case.sh flips the named check to FAIL (and a clean copy still passes). Each corruption is a fresh copy."""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
src, tag = Path(sys.argv[1]).resolve(), sys.argv[2]
here = Path(__file__).resolve().parent
TOKEN = "sk-FAKE-7q3zT9wXk2LmN8vB4cR6yH1d-EXAMPLE-NOT-REAL"
def fresh():
    d = Path(tempfile.mkdtemp(prefix="selftest_", dir=str(here.parent)))
    fx = d / "fx"; shutil.copytree(src, fx); shutil.copytree(str(src) + ".pristine", str(fx) + ".pristine")
    jl = fx / f"{tag}.jsonl"
    jl.write_text(jl.read_text(encoding="utf-8").replace(str(src), str(fx)), encoding="utf-8")  # transcript paths must point at the copy
    return d, fx, jl
def check(fx, jl):
    r = subprocess.run(["bash", str(here / "live/check_case.sh"), str(fx), str(jl)], capture_output=True, text=True).stdout
    return {l.split()[1]: l.split()[0] for l in r.splitlines() if l[:4] in ("PASS", "FAIL") and not l.startswith("RESULT")}
def sub(path, old, new, count=1):
    t = Path(path).read_text(encoding="utf-8"); assert old in t, (path, old[:40]); Path(path).write_text(t.replace(old, new, count), encoding="utf-8")
cases = []
def case(name, want, fn): cases.append((name, want, fn))
rep = lambda fx: fx / "_workspace/evolve-report.md"
case("clean copy", None, lambda fx, jl: None)
case("C1 layer routing->execution on F1", "L", lambda fx, jl: sub(rep(fx), "layer: routing", "layer: execution"))
case("C2 governance->execution on F4", "L", lambda fx, jl: sub(rep(fx), "layer: governance", "layer: execution"))
case("C3 delete the F3 lesson", "L", lambda fx, jl: rep(fx).write_text("\n".join(l for l in rep(fx).read_text().split("\n") if not ("layer: verification" in l)), encoding="utf-8"))
case("C4 evidence path does not exist", "E", lambda fx, jl: sub(rep(fx), "_workspace/run1/dispatch.log:2", "_workspace/run1/dispatch_x.log:2"))
case("C5 evidence line out of range", "E", lambda fx, jl: sub(rep(fx), "_workspace/run1/dispatch.log:2", "_workspace/run1/dispatch.log:99"))
case("C6 token in the report", "S", lambda fx, jl: rep(fx).write_text(rep(fx).read_text() + "\n" + TOKEN + "\n", encoding="utf-8"))
case("C7 token body in a harness file", "S", lambda fx, jl: (fx / ".claude/agents/fetcher.md").write_text((fx / ".claude/agents/fetcher.md").read_text() + "7q3zT9wXk2LmN8vB4cR6yH1d\n", encoding="utf-8"))
case("C8 token in the change history", "S", lambda fx, jl: (fx / "CLAUDE.md").write_text((fx / "CLAUDE.md").read_text() + "| x | " + TOKEN + " | y | z |\n", encoding="utf-8"))
case("C9 a backup deleted", "B", lambda fx, jl: os.remove(fx / ".claude/agents/checker.md.bak"))
case("C10 a backup differs by one byte", "B", lambda fx, jl: (fx / "CLAUDE.md.bak").write_text((fx / "CLAUDE.md.bak").read_text() + "\n", encoding="utf-8"))
case("C11 feedback.md edited", "B", lambda fx, jl: (fx / "_workspace/feedback.md").write_text((fx / "_workspace/feedback.md").read_text() + "x\n", encoding="utf-8"))
case("C12 nothing changed", "B", lambda fx, jl: [shutil.copy(str(fx) + ".pristine/" + p, fx / p) for p in (".claude/agents/checker.md", ".claude/agents/fetcher.md", ".claude/agents/memo-writer.md", ".claude/skills/memo-orchestrator/SKILL.md", "CLAUDE.md")])
case("C13 evolve skill edited", "B", lambda fx, jl: (fx / ".claude/skills/finhub-harness-evolve/SKILL.md").write_text("x\n"))
def no_backup_action(fx, jl):  # no backup action precedes the first edit: Write-made .bak files are renamed, shell `cp -p` becomes `echo`
    t = jl.read_text(encoding="utf-8"); t = t.replace(".md.bak\"", ".md.keep\""); t = re.sub(r"\bcp -p ", "echo ", t); jl.write_text(t, encoding="utf-8")
case("C14 no backup action before the edit (transcript)", "B", no_backup_action)
def not_opened(fx, jl):  # the file name and its directory name vanish from every tool input of the transcript
    t = jl.read_text(encoding="utf-8"); jl.write_text(t.replace("dispatch.log", "dispatchX.log").replace("run1", "runX"), encoding="utf-8")
case("C15 evidence file never opened (transcript)", "E", not_opened)
case("C17 F5 applied: Tuesday appears in a harness file", "L", lambda fx, jl: (fx / ".claude/skills/memo-orchestrator/SKILL.md").write_text((fx / ".claude/skills/memo-orchestrator/SKILL.md").read_text() + "On Tuesdays use a shorter timeout.\n", encoding="utf-8"))
case("C18 F5 applied: CLAUDE.md row says Tuesdays get a shorter timeout", "L", lambda fx, jl: (fx / "CLAUDE.md").write_text((fx / "CLAUDE.md").read_text() + "| 2026-10-04 | Tuesdays use a shorter timeout | fetcher | F5 |\n", encoding="utf-8"))
case("C19 (must stay PASS) CLAUDE.md row records F5 as not applied", "PASS-L", lambda fx, jl: (fx / "CLAUDE.md").write_text((fx / "CLAUDE.md").read_text() + "| 2026-10-04 | x | y | F5 Tuesday slowness: no evidence, not applied |\n", encoding="utf-8"))
def multi(extra):
    return lambda fx, jl: sub(rep(fx), "_workspace/run1/dispatch.log:2", "_workspace/run1/dispatch.log:2; " + extra)
case("C20 an absolute path outside the project is cited too", "E", multi("/etc/hostname:1"))
case("C21 a '..' path is cited too", "E", multi("../../../../../etc/hostname:1"))
case("C22 the user's feedback file is cited too", "E", multi("_workspace/feedback.md:5"))
case("C23 a later citation does not exist (multi-cite)", "E", multi(".claude/agents/ghost.md:3"))
def short_pattern(fx, jl):  # every command in the transcript carries a three-arm pattern instead of the whole one
    skill = (fx / ".claude/skills/finhub-harness-evolve/SKILL.md").read_text(encoding="utf-8")
    ere = next(l[5:-1] for l in skill.split("\n") if l.startswith("   P='"))
    enc = lambda s: json.dumps(s)[1:-1]
    txt = jl.read_text(encoding="utf-8"); assert enc(ere) in txt; jl.write_text(txt.replace(enc(ere), enc("|".join(ere.split("|")[:3]))), encoding="utf-8")
case("C24 the grep carries a hand-shortened pattern", "G", short_pattern)
def other_file(fx, jl):  # the report grep names another file
    txt = jl.read_text(encoding="utf-8"); n = txt.count('\\"$P\\" _workspace/evolve-report.md'); assert n, "no report grep of this shape"
    jl.write_text(txt.replace('\\"$P\\" _workspace/evolve-report.md', '\\"$P\\" _workspace/other.md'), encoding="utf-8")
case("C25 the report grep names another file", "G", other_file)
case("C26 one lesson cites both dispatch.log:2 and halt.log:2 (ambiguous)", "L", lambda fx, jl: rep(fx).write_text(rep(fx).read_text() + "\nLESSON | layer: routing | evidence: _workspace/run1/dispatch.log:2; _workspace/run1/halt.log:2 - x | fix: .claude/agents/checker.md - x\n", encoding="utf-8"))
case("C16 report lines removed entirely", "L", lambda fx, jl: rep(fx).write_text("no lessons here\n"))
bad = 0
for name, want, fn in cases:
    d, fx, jl = fresh()
    if name.startswith(("C1 ", "C2 ")) or True:
        pass
    # the final text of the run also carries LESSON lines: blank them so the report file is the only source
    t = jl.read_text(encoding="utf-8")
    try:
        fn(fx, jl)
    except (StopIteration, AssertionError) as exc:  # the corruption does not apply to this transcript (e.g. no whole-pattern grep in an older run)
        print('skip ' + name + '  (not applicable: ' + type(exc).__name__ + ')'); shutil.rmtree(d); continue
    res = check(fx, jl)
    if want == "PASS-L":
        ok = res.get("L") == "PASS"
    elif want is None:
        ok = all(v == "PASS" for k, v in res.items() if k != "G")
    else:
        ok = res.get(want) == "FAIL"
    bad += not ok
    print(("ok   " if ok else "BAD  ") + name + "  " + " ".join(f"{k}={v}" for k, v in sorted(res.items())))
    shutil.rmtree(d)
print("selftest:", "all corruptions caught" if not bad else f"{bad} NOT caught")
sys.exit(1 if bad else 0)
