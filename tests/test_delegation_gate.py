"""Proof for the delegation decision gate in SKILL.md 2-0, team-patterns.md 6-1 and Template C (C15).

Two tests read references/meta_harness and skip when it is not checked out (CI does not fetch
submodules). QA runs this file with the submodule present and requires 0 skipped
(`pytest -q -rs tests/test_delegation_gate.py`).
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO / "skills/finhub-harness"
SKILL = SKILL_DIR / "SKILL.md"
PATTERNS = SKILL_DIR / "references/team-patterns.md"
TEMPLATE = SKILL_DIR / "references/orchestrator-template.md"
LINT = SKILL_DIR / "scripts/lint_harness.py"
MH = REPO / "references/meta_harness"
PATTERNS_SRC = ".agents/skills/harness/references/agent-design-patterns.md"
TEMPLATE_SRC = ".agents/skills/harness/references/orchestrator-template.md"
SKILL_SRC = ".agents/skills/harness/SKILL.md"
# question number -> every pattern that must appear in that question, in all three files
KEYS = [
    [r"independent", r"hand off"],
    [r"specialisation", r"parallel speed", r"separate context"],
    [r"\bwrite"],
    [r"tools", r"permissions"],
    [r"synthes"],
    [r"partial", r"blocked", r"conflicting"],
]
# the decision rule of each row: the whole "Unclear when" cell, so a negation or edit fails
UNCLEAR = [
    "the units cannot be listed, or a hand-off exists but the artefact handed over is not named",
    'the answer is "more thorough", or none of the three',
    (
        "two workers that run at the same time can write the same path or resource, "
        "or the paths are not named (writers that run one after another are fine)"
    ),
    "a worker needs a connector, tool or permission it was not given, or the surface lacks it",
    'nobody is named, or the answer is "the workers"',
    "the orchestrator would fill the gap with a guess or pick a winner silently",
]
CHAIN = ("pipeline", "producer-reviewer", "Mode B", "fresh-context judge")
RETRY = r"retry|retries|again|re-ask|repeat|re-run|loop"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def between(text: str, start: str, end: str) -> str:
    assert text.count(start) == 1, (start, text.count(start))
    i = text.index(start)
    return text[i : text.index(end, i + len(start))]


def skill_gate() -> str:
    return between(read(SKILL), "#### 2-0.", "#### 2-1.")


def patterns_gate() -> str:
    return between(read(PATTERNS), "### 6-1.", "## 7. Designing")


def template_c() -> str:
    return between(read(TEMPLATE), "## Template C:", "## Combining execution modes")


def first_sentence(text: str) -> str:
    return re.split(r"(?<=\.)\s", text.strip(), maxsplit=1)[0]


def bullets(block: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^- (.+)$", block, re.MULTILINE)]


def bullet(block: str, start: str) -> str:
    return next(b for b in bullets(block) if b.startswith(start))


def paragraph(block: str, start: str) -> str:
    return next(p for p in block.split("\n\n") if p.startswith(start))


def default_para() -> str:
    return next(p for p in patterns_gate().split("\n\n") if "stay with one agent" in p)


def template_gate() -> str:
    return between(template_c(), "## Delegation gate", "## Worker delegation notes")


def template_notes() -> str:
    return between(template_c(), "## Worker delegation notes", "## Work procedure")


def template_errors() -> str:
    return template_c().split("## Error handling", 1)[1]


def has_all(text: str, keys: list[str]) -> bool:
    return all(re.search(k, text, re.IGNORECASE) for k in keys)


def test_six_questions_agree_across_the_three_files() -> None:
    rows = re.findall(r"^\| (\d) \| (.+?) \| (.+?) \|$", patterns_gate(), re.MULTILINE)
    assert [r[0] for r in rows] == ["1", "2", "3", "4", "5", "6"]
    for (_, question, _unclear), keys in zip(rows, KEYS, strict=True):
        assert has_all(question, keys), (question, keys)
    chunks = re.split(r"\(([1-6])\) ", skill_gate().split("\n\n")[1])
    assert chunks[1::2] == ["1", "2", "3", "4", "5", "6"]
    for chunk, keys in zip(chunks[2::2], KEYS, strict=True):
        assert has_all(chunk, keys), (chunk, keys)
    items = bullets(template_gate())
    assert len(items) == 8 and items[6].startswith("Outcome:") and items[7].startswith("Risks")
    for item, keys in zip(items[:6], KEYS, strict=True):
        assert has_all(item, keys), (item, keys)


def test_each_unclear_condition_is_the_stated_rule() -> None:
    rows = re.findall(r"^\| \d \| .+? \| (.+?) \|$", patterns_gate(), re.MULTILINE)
    assert rows == UNCLEAR


def test_unclear_means_single_agent_in_every_file() -> None:
    unclear = bullet(skill_gate(), "If any answer is missing")
    assert unclear.startswith("If any answer is missing or unclear")
    lead = first_sentence(unclear)
    assert "single agent" in lead and not re.search(r"delegate|multi|team", lead)
    assert not re.search(r"\b(unless|except|but)\b|\bthe user\b", unclear)  # no escape hatch here
    only = bullet(skill_gate(), "Only when all six")
    assert re.search(r"all six answers are concrete is the outcome \*\*delegate\*\*", only)
    para = default_para()
    assert re.search(r"unclear.*(one|single) agent", first_sentence(para))
    assert not re.search(r"split|delegate|parallel|team", first_sentence(para))
    intro = template_gate().splitlines()[1]
    assert re.search(r"unclear answer means a single agent", intro)
    outcome = template_gate().split("- Outcome:", 1)[1].splitlines()[0]
    assert outcome.index("single agent") < outcome.index("delegate")


def test_single_agent_outcome_is_defined_and_scoped_for_extensions() -> None:
    unclear = bullet(skill_gate(), "If any answer is missing")
    lead = first_sentence(unclear)
    assert re.search(r"main (context|thread|agent) does the work", lead)
    assert "at most one agent file" in lead
    assert "no Mode A or B" in lead and "no parallel workers" in lead
    assert re.search(r"not a reason to delegate", unclear)
    assert re.search(r"extension.*counts the new role only.*not a new file", unclear)
    step2 = between(template_c(), "### Step 2:", "### Step 3:")
    assert step2.index("only when the gate's outcome is delegate") < step2.index("Call the Agent")
    assert re.search(r"main agent does the work in this context", step2)
    assert "Steps 3 and 4 apply to its own output" in step2


def test_single_agent_orchestrator_stops_declaring_mode_c() -> None:
    intro = template_gate().splitlines()[1]
    assert (
        "replace the `## Execution mode` heading above with `## Execution mode: Single agent`"
        in intro
    )
    assert re.search(r'description\'s "Delegates \.\.\. to sub-agents" wording', intro)
    c = template_c()
    assert "## Execution mode: Sub-agent delegation (Mode C)" in c
    assert 'description: "Delegates independent {domain} tasks to sub-agents.' in c
    assert c.index("description:") < c.index("## Execution mode") < c.index("## Delegation gate")


def test_coordinator_layer_needs_a_reason_and_the_two_level_cap_stays() -> None:
    coordinator = bullet(skill_gate(), "A coordinator layer")
    assert re.search(r"needs one sentence in the orchestrator that names why", coordinator)
    assert re.search(r"without it, workers report to the root", coordinator)
    assert re.search(r"two-level cap in 2-2 stays", coordinator)
    para = paragraph(patterns_gate(), "Of the two levels")
    assert re.search(r"needs a one-sentence reason in the orchestrator", para)
    assert re.search(r"Without it, workers report to the root", para)
    # the existing rule is built on, not restated or weakened
    assert read(SKILL).count("two levels at most") == 1
    assert read(PATTERNS).count("Two levels or fewer is recommended") == 1


def test_tool_availability_is_not_a_reason_to_split() -> None:
    para = default_para()
    assert re.search(r"shows what is possible on a surface, not that splitting pays", para)


def test_dependent_chains_pass_when_hand_offs_are_named() -> None:
    for text in (
        bullet(skill_gate(), "A dependent chain"),
        default_para(),
    ):
        for term in CHAIN:
            assert term in text, term
        assert "design then judge then build then QA" in text
        assert re.search(r"concrete when each hand-off artefact is named", text)
        assert re.search(r"delegates in sequence", text)
        assert re.search(r"independence only decides whether calls run in parallel", text)
    worked = paragraph(patterns_gate(), "Worked answers")
    assert re.search(
        r"design, a fresh judge, a build and a QA step.*passes, as a sequential team", worked
    )
    assert re.search(r'"do it in parallel" with no units listed fails question 1', worked)
    assert "stays with one agent" in worked


def test_explicit_team_request_is_built_with_risks_recorded() -> None:
    clauses = (
        bullet(skill_gate(), "When the user explicitly asks"),
        paragraph(patterns_gate(), "When the user explicitly asks"),
    )
    for clause in clauses:
        first, last = first_sentence(clause), clause.strip().split(". ")[-1]
        assert re.search(r"build what was asked", first)
        assert not re.search(r"single", first)  # the default never overrides the request
        assert re.search(r"each unclear answer under `## Delegation gate` as a stated risk", clause)
        assert re.search(r"tell the user", clause)
        assert re.search(r"single-agent default applies when the user has not chosen", last)
    intro = template_gate().splitlines()[1]
    assert re.search(r"If the user explicitly asked for a team, build it anyway", intro)
    assert "Risks (only when the user explicitly asked for a team)" in template_gate()


def test_gate_comes_first_and_composes_with_scale_and_extend() -> None:
    text = read(SKILL)
    positions = [text.index(h) for h in ("### Step 2:", "#### 2-0.", "#### 2-1.", "#### 2-2.")]
    assert positions == sorted(positions)
    para = paragraph(patterns_gate(), "Run the gate")
    assert re.search(r"^Run the gate before the table above", para)
    assert not re.search(r"after the table|table decides", para)
    only = bullet(skill_gate(), "Only when all six")
    assert re.search(r"then 2-1 to 2-3 and the Step 5 scale rule size the team", only)
    assert "run the gate again for the new role alone" in only
    scale = bullet(text, "**Scale**")
    assert scale.startswith("**Scale**: 2-3 persistent agents")  # unchanged, now behind the gate
    step5 = between(text, "- **Delegation contract**", "- **Scale**")
    record = bullet(step5, "**Delegation gate**")
    assert record.startswith("**Delegation gate** (every orchestrator):")
    assert "only" not in record.split(":")[0]
    assert "`## Delegation gate` section with the six answers and the outcome" in record
    assert "written before anything is spawned" in record
    assert "a single-agent outcome spawns nothing" in record
    assert "an A or B orchestrator copies the same block" in record
    assert step5.index("**Delegation gate**") < step5.index("**Error policy**")
    assert "`## Delegation gate`" in skill_gate()


def test_template_c_notes_and_error_rows() -> None:
    assert template_c().index("## Delegation gate") < template_c().index("### Step 0")
    head = "## Worker delegation notes (optional; keep only when the outcome is delegate)"
    assert head in template_notes()
    fields = [b.split(":")[0] for b in bullets(template_notes())]
    assert fields == [
        "Eligible tasks",
        "Forbidden overlaps (paths, resources, topics)",
        "Synthesis owner and what they accept",
        "Conflicting-result rule",
    ]
    errors = bullets(template_errors())
    assert len(errors) == 5  # three existing rows plus the two added
    partial = next(e for e in errors if "`partial` or `blocked`" in e)
    assert "keep what it returned" in partial and "mark the result incomplete" in partial
    assert "Do not cover the missing part with a guess" in partial
    missing = next(e for e in errors if e.startswith("A synthesis input that never arrives"))
    assert "mark each missing branch as missing in the final artifact and in the report" in missing
    assert "Do not write text that implies coverage the run lacks" in missing
    for row in (partial, missing):  # no new retry loop: the Delegation contract has the one re-ask
        assert not re.search(RETRY, row, re.IGNORECASE), row


def test_attribution_names_the_source_line_and_licence_in_each_file() -> None:
    expect = {
        SKILL: [(PATTERNS_SRC, 221), (SKILL_SRC, 166)],
        PATTERNS: [(PATTERNS_SRC, 221), ("docs/architecture/role-contract.md", 49)],
        TEMPLATE: [(TEMPLATE_SRC, 78), ("docs/architecture/handoffs.md", 34)],
    }
    for path, cites in expect.items():
        text = read(path)
        for rel, line in cites:
            assert f"adapted from references/meta_harness/{rel}:{line} (Apache-2.0)" in text, (
                path.name,
                rel,
            )


CITED = [
    (PATTERNS_SRC, 221, "## Delegation Decision Gate"),
    (PATTERNS_SRC, 232, "If those answers are unclear"),
    (SKILL_SRC, 166, "Delegate only when"),
    (TEMPLATE_SRC, 78, "## Optional Worker Delegation Notes"),
    ("docs/architecture/handoffs.md", 34, "Every delegated workflow must account"),
    ("docs/architecture/role-contract.md", 49, "Keep delegation shallow"),
]
NO_SUBMODULE = (
    "references/meta_harness is not checked out (CI does not fetch submodules); QA must run "
    "this file with it present and require 0 skipped (pytest -q -rs)"
)


def test_cited_source_lines_still_say_what_the_claim_needs() -> None:
    if not MH.is_dir() or not any(MH.iterdir()):
        pytest.skip(NO_SUBMODULE)
    for rel, line, token in CITED:
        lines = read(MH / rel).splitlines()
        assert token in lines[line - 1], (rel, line, lines[line - 1])


def grams(text: str, n: int = 8) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {tuple(words[i : i + n]) for i in range(len(words) - n + 1)}


def test_no_eight_word_run_is_copied_from_the_source() -> None:
    if not MH.is_dir() or not any(MH.iterdir()):
        pytest.skip(NO_SUBMODULE)
    source: set[tuple[str, ...]] = set()
    for rel in (PATTERNS_SRC, SKILL_SRC, TEMPLATE_SRC, *(c[0] for c in CITED[4:])):
        source |= grams(read(MH / rel))
    step2 = between(template_c(), "### Step 2:", "### Step 3:")
    errors = template_errors().split("```", 1)[0]
    added = f"{skill_gate()}\n{patterns_gate()}\n{template_gate()}\n{template_notes()}\n{step2}\n{errors}"
    assert grams(added) & source == set()


def test_no_hangul_in_the_changed_files() -> None:
    ranges = ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))
    for path in (SKILL, PATTERNS, TEMPLATE, Path(__file__)):
        text = read(path)
        assert not any(lo <= ord(c) <= hi for c in text for lo, hi in ranges), path


def test_template_c_still_lints_clean_when_filled_in(tmp_path: Path) -> None:
    block = re.search(r"```markdown\n(.*?)\n```\n", template_c(), re.DOTALL)
    assert block, "Template C code fence not found"
    filled = block.group(1).replace("{domain}", "demo").replace("{initial run keywords}", "demo")
    filled = re.sub(r"\{[^{}\n]+\}", "x", filled)
    skill = tmp_path / "skills/demo-orchestrator/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(filled, encoding="utf-8")
    run = subprocess.run(
        [sys.executable, str(LINT), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    out = run.stdout + run.stderr
    assert run.returncode == 0, out
    assert "lazy-delegation" not in out and "ERROR" not in out, out
    assert "## Delegation gate" in filled and "## Worker delegation notes" in filled


def test_unclear_rule_is_any_not_all() -> None:  # X07
    first = first_sentence(default_para())
    assert re.match(r"(Any unclear answer|If any answer is unclear)", first), first
    assert not re.search(r"\b(all|every)\b", first, re.IGNORECASE), first


def test_explicit_request_trigger_phrase_is_pinned() -> None:  # X05
    phrase = "explicitly asks for a team or names the roles"
    assert phrase in bullet(skill_gate(), "When the user explicitly asks")
    assert phrase in paragraph(patterns_gate(), "When the user explicitly asks")


def test_chain_sentences_do_not_widen_the_pass() -> None:  # X06, X06b
    for text in (bullet(skill_gate(), "A dependent chain"), default_para()):
        for widener in ("implied", "unnamed", "or described", "is fine too"):
            assert widener not in text, widener


def test_template_c_step_2_calls_dependent_hand_offs_in_sequence() -> None:  # X16, A20
    step2 = between(template_c(), "### Step 2", "### Step 3")
    assert (
        "dependent hand-offs are called one after another, each with the prior artefact path"
        in step2
    )
