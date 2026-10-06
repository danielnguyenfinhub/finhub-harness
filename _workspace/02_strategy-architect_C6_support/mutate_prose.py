import re, shutil, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).parent
T = "skills/finhub-harness/references/orchestrator-template.md"
S = "skills/finhub-harness/SKILL.md"
U = "skills/finhub-harness/references/surfaces.md"
apply_src = (ROOT / "apply.py").read_text()
section = [l for l in (ROOT / "section.md").read_text().split("\n") if l.strip() and l not in ("```", "````", "````markdown")]
p10 = re.search(r'insert_after\(T, "9\. [^\n]*\n"(10\. .*?)"\)', apply_src, re.S).group(1)
bul = re.search(r'"(- \*\*Delegation contract\*\*.*?)"\)', apply_src, re.S).group(1)
chk = re.search(r'"(- \[ \] Every worker brief.*?)"\)', apply_src, re.S).group(1)
row = re.search(r'"(\| 8 \| Delegation contract \|.*?)"\)', apply_src, re.S).group(1)
subs = [
 (S, 'that `## Required connectors` lines and the preflight table agree, that no agent or skill file which calls `Agent(`, `agent(`, `Task(` or `SendMessage`, or names `subagent_type` or `agentType`, contains a lazy-delegation phrase (WARN `lazy-delegation`), and v1 artefacts;'),
 (S, " Delegation, wherever workers are spawned or messaged — `grep -l 'STATUS:' project/.claude/skills/*/SKILL.md` lists the orchestrator. Where the lint cannot run, `grep -nEi 'based on (your|the) (findings|research)|as (we )?discussed' project/.claude/skills/*/SKILL.md project/.claude/agents/*.md` is a stricter manual fallback (no word boundaries, every file, blind to a phrase wrapped over two lines): judge each hit by hand, because a research-and-write skill may legitimately keep one."),
]
whole = [(T, l) for l in [p10] + section] + [(S, bul), (S, chk), (U, row)]
def check(d: Path):
    bad = []
    cache = {}
    for f, l in whole:
        t = cache.setdefault(f, (d / f).read_text().split("\n"))
        if t.count(l) != 1: bad.append((f, l[:50]))
    for f, s in subs:
        t = cache.setdefault(f + "#", (d / f).read_text())
        if t.count(s) != 1: bad.append((f, s[:50]))
    return bad
def mk():
    d = Path(tempfile.mkdtemp(dir=ROOT.parent))
    shutil.copytree(ROOT / "skills", d / "skills")
    return d
assert not check(ROOT), check(ROOT)
print("baseline clean; inserted whole lines:", len(whole), "substrings:", len(subs))
SEM = [  # (id, file, old, new)
 ("P01 drop Goal line", T, "- Goal: one sentence", "- Aim: one sentence"),
 ("P02 drop Inputs line", T, "- Inputs: the exact paths", "- Sources: the exact paths"),
 ("P03 drop Scope disjoint rule", T, " Workers running in parallel get disjoint scopes.", ""),
 ("P04 Expected output -> optional", T, "- Expected output: the file under", "- Optional output: the file under"),
 ("P05 drop Report line", T, "- Report: end the reply with the Worker report below.", "- Report: free form."),
 ("P06 drop 'partial' status", T, "STATUS: complete | partial | blocked", "STATUS: complete | blocked"),
 ("P07 drop 'blocked' status", T, "STATUS: complete | partial | blocked", "STATUS: complete | partial"),
 ("P08 evidence threshold 1 -> 0", T, "EVIDENCE has at least one item, and there is no BLOCKER or NEXT STEPS", "EVIDENCE may be empty, and there is no BLOCKER or NEXT STEPS"),
 ("P09 complete may carry BLOCKER", T, "EVIDENCE has at least one item, and there is no BLOCKER or NEXT STEPS", "EVIDENCE has at least one item"),
 ("P10 partial threshold", T, "NEXT STEPS has at least one item, and there is no BLOCKER", "NEXT STEPS may be empty, and there is no BLOCKER"),
 ("P11 blocked needs no concrete blocker", T, "| blocked | BLOCKER names something concrete |", "| blocked | BLOCKER is present |"),
 ("P12 re-ask once -> twice", T, "Re-ask once: tell the worker", "Re-ask twice: tell the worker"),
 ("P13 re-ask unbounded", T, "do not ask again: record", "keep asking: record"),
 ("P14 second failure accepted", T, "record the result as unverified in `_workspace/`, say so in the final report, and take nothing from it as fact", "accept the result as complete"),
 ("P15 SendMessage branch dropped", T, "Use `SendMessage` for a named worker; ", ""),
 ("P16 one-shot branch dropped", T, "for a one-shot worker launch it once more with the same brief plus that sentence; ", ""),
 ("P17 Workflow branch dropped", T, "in a Workflow script make one second `agent()` call the same way.", "."),
 ("P18 blocked-valid sentence dropped", T, "A `blocked` report with a concrete BLOCKER is valid; handle it with the error table, and do not retry authentication, permission or usage-limit failures.", ""),
 ("P19 fallback exclusion dropped", T, "Never paste it into a `## Single-context fallback`: a role pass has no separate worker, and the fallback may not name `Agent` or `SendMessage` (`surfaces.md` section 5).", ""),
 ("P20 lazy phrase list narrowed", T, "\"based on the research\" (also \"the findings\", \"your research\")", "\"based on the research\""),
 ("P21 lazy phrase seeded in block", T, "- Goal: one sentence, and what", "- Goal: based on your findings, one sentence, and what"),
 ("P22 attribution OH removed", T, "(adapted from references/openharness/src/openharness/coordinator/coordinator_mode.py:407 (MIT); ", "("),
 ("P23 attribution O32 removed", T, "adapted from references/openhands/src/api/launch-child-conversation-client-tool.ts:32 (MIT))", ")"),
 ("P24 attribution D54 removed", T, " (adapted from references/deepseek_harness/packages/workflow/tool-ralph/src/index.ts:112 (MIT))", ""),
 ("P25 attribution C38 removed", T, " (adapted from references/crewai/lib/crewai/src/crewai/task.py:1327 (MIT))", ""),
 ("P26 principle 10 removed", T, "10. **Give every worker a self-contained brief", "11. **Give every worker a self-contained brief"),
 ("P27 SKILL Step 5 bullet removed", S, "- **Delegation contract** (only when", "- **Delegation** (only when"),
 ("P28 Step 6.1 lint clause reverted", S, "that no agent or skill file which calls `Agent(`, `agent(`, `Task(` or `SendMessage`, or names `subagent_type` or `agentType`, contains a lazy-delegation phrase (WARN `lazy-delegation`), and v1 artefacts;", "and v1 artefacts;"),
 ("P28b Step 6.1 clause drops a token", S, "`Task(` or `SendMessage`, or names", "`Task(`, or names"),
 ("P29 Step 6.2 STATUS grep dropped", S, "`grep -l 'STATUS:' project/.claude/skills/*/SKILL.md` lists the orchestrator. ", ""),
 ("P30 Step 6.2 grep alt 'as discussed' dropped", S, "|as (we )?discussed' project/.claude", "' project/.claude"),
 ("P31 Step 6.2 grep alt 'findings' dropped", S, "(findings|research)|as (we )?discussed' project", "(research)|as (we )?discussed' project"),
 ("P32 Step 6.2 grep: agents dir dropped", S, " project/.claude/agents/*.md` is a stricter", "` is a stricter"),
 ("P32b Step 6.2 'same test' restored", S, "is a stricter manual fallback", "is the same test as the lint"),
 ("P32c Step 6.2 'judge each hit by hand' dropped", S, ": judge each hit by hand, because a research-and-write skill may legitimately keep one.", "."),
 ("P37 re-ask is the only retry sentence dropped", T, "This re-ask is the only retry for an invalid report; the general retry-once rule does not add a second. ", ""),
 ("P38 limits: never opens dropped", T, "never opens it, so an invented path passes", "is thorough, so an invented path fails"),
 ("P39 limits: UNVERIFIED Mode A dropped", T, "how a Mode A `schema` result carries STATUS is UNVERIFIED", "a Mode A `schema` result carries STATUS"),
 ("P40 attribution claim for 'as discussed' restored", T, "\"as discussed\" is not from any reference", "\"as discussed\" is from OpenHarness"),
 ("P41 lint scope sentence dropped", T, "it reads only `agents/*.md` and `skills/**/SKILL.md`, so a brief kept in a `references/` file is not scanned", "it reads every file"),
 ("P42 lint scope token list narrowed", T, "`subagent_type`, `agentType`, `SendMessage`, `agent(`, `Agent(` or `Task(`", "`subagent_type` or `agentType`"),
 ("P33 checklist item removed", S, "- [ ] Every worker brief has Goal", "- [ ] Each worker brief has Goal"),
 ("P34 surfaces row removed", U, "| 8 | Delegation contract |", "| 8 | Delegation |"),
 ("P35 surfaces: chat claim flipped", U, "chat exposes no sub-agent tool (section 2)", "chat exposes sub-agent tools (section 2)"),
 ("P36 limits paragraph dropped", T, "Limits. The check confirms that an evidence item", "Note. The check confirms that an evidence item"),
]
res = {"k": 0, "s": 0}
def run(name, f, old, new):
    d = mk()
    t = (d / f).read_text()
    assert old in t, (name, "old not found")
    (d / f).write_text(t.replace(old, new, 1))
    bad = check(d)
    shutil.rmtree(d)
    res["k" if bad else "s"] += 1
    print(f"{name:45} {'KILLED' if bad else 'SURVIVED'}")
for m in SEM: run(*m)
if "--sweep" in sys.argv:
    for f, l in whole:
        run("delete whole line: " + l[:30], f, l + "\n", "")
print(res)
