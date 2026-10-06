"""Apply the C6 insertions to the scratch copy (cwd = scratch root). Anchors are exact line starts."""
from pathlib import Path

def insert_after(path, startswith, text, expect_unique=True):
    p = Path(path)
    lines = p.read_text(encoding="utf-8").split("\n")
    hits = [i for i, l in enumerate(lines) if l.startswith(startswith)]
    assert len(hits) == 1, (path, startswith, hits)
    lines[hits[0] + 1 : hits[0] + 1] = text.split("\n")
    p.write_text("\n".join(lines), encoding="utf-8")

def insert_before(path, startswith, text):
    p = Path(path)
    lines = p.read_text(encoding="utf-8").split("\n")
    hits = [i for i, l in enumerate(lines) if l.startswith(startswith)]
    assert len(hits) == 1, (path, startswith, hits)
    lines[hits[0] : hits[0]] = text.split("\n")
    p.write_text("\n".join(lines), encoding="utf-8")

def replace_once(path, old, new):
    p = Path(path)
    t = p.read_text(encoding="utf-8")
    assert t.count(old) == 1, (path, old, t.count(old))
    p.write_text(t.replace(old, new), encoding="utf-8")

T = "skills/finhub-harness/references/orchestrator-template.md"
S = "skills/finhub-harness/SKILL.md"
U = "skills/finhub-harness/references/surfaces.md"

# E1 principle 10
insert_after(T, "9. **Do not include items that existed only in v1.**",
"10. **Give every worker a self-contained brief and require a report you can check.** Paste the Delegation block below into the orchestrator once, at the step that launches or messages workers, and fill one brief per worker role.")

# E2 section, before the follow-up phrasings heading
SECTION = open("section.md", encoding="utf-8").read().rstrip("\n") + "\n"
insert_before(T, "## Follow-up request phrasings to put in `description`", SECTION)

# E3 SKILL.md Step 5 bullet after Data hand-off
insert_after(S, "- **Data hand-off**:",
"- **Delegation contract** (only when the orchestrator spawns or messages a worker, so never in a single-context fallback): paste the Delegation block from `references/orchestrator-template.md` at the step that launches workers and fill one five-line brief per worker role. The block fixes what a brief must contain, the STATUS / EVIDENCE / BLOCKER report a worker ends with, and the check the orchestrator runs before it uses a report (re-ask once, then mark the result unverified). It is prompt quality plus a check, not a guarantee.")

# E4 Step 6.1 lint list
replace_once(S, "that `## Required connectors` lines and the preflight table agree, and v1 artefacts;",
"that `## Required connectors` lines and the preflight table agree, that no agent or skill file which calls `Agent(`, `agent(`, `Task(` or `SendMessage`, or names `subagent_type` or `agentType`, contains a lazy-delegation phrase (WARN `lazy-delegation`), and v1 artefacts;")

# E5 Step 6.2 delegation sentence
replace_once(S, "mixed — mode written per phase and hand-offs unbroken. Chat/Cowork targets — the single-context fallback covers every phase.",
"mixed — mode written per phase and hand-offs unbroken. Chat/Cowork targets — the single-context fallback covers every phase. Delegation, wherever workers are spawned or messaged — `grep -l 'STATUS:' project/.claude/skills/*/SKILL.md` lists the orchestrator. Where the lint cannot run, `grep -nEi 'based on (your|the) (findings|research)|as (we )?discussed' project/.claude/skills/*/SKILL.md project/.claude/agents/*.md` is a stricter manual fallback (no word boundaries, every file, blind to a phrase wrapped over two lines): judge each hit by hand, because a research-and-write skill may legitimately keep one.")

# E6 checklist
insert_after(S, "- [ ] Every `## Required connectors` line in an agent file",
"- [ ] Every worker brief has Goal, Inputs, Scope, Expected output and Report; every worker report ends in STATUS / EVIDENCE / BLOCKER form; the orchestrator re-asks once and then marks the result unverified.")

# E7 surfaces.md row 8
insert_after(U, "| 7 | Connector preflight |",
"| 8 | Delegation contract | The Delegation block (`orchestrator-template.md`) is in every section that spawns or messages a worker, and in no Single-context fallback. Code only: chat exposes no sub-agent tool (section 2), Cowork is unverified |")
print("applied")
