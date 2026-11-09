"""Round-3 plugin re-audit (P2-1 to P2-9): lint false negatives, tracker keys and state, README, light skill."""

from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
LINT = REPO / "skills/finhub-harness/scripts/lint_harness.py"
TRACKER = REPO / "skills/finhub-harness/scripts/unit_tracker.py"
RULE = "connector-tools-unscoped"
IMPLICIT = "send-implicit"
SENDER = "Sending worker: makes only the calls on the approved list."


def lint(root: Path) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(LINT), str(root)], capture_output=True, text=True, check=False
    )
    return p.returncode, p.stdout


def harness(
    root: Path, agent_extra: str, body: str, heading: str = "## Ask before an outside effect"
) -> str:
    orch = root / "skills" / "orch"
    orch.mkdir(parents=True, exist_ok=True)
    (orch / "SKILL.md").write_text(
        f'---\nname: orch\ndescription: "D. Use when X."\ndisable-model-invocation: true\n---\n{heading}\n'
    )
    (root / "agents").mkdir(exist_ok=True)
    (root / "agents" / "w.md").write_text(
        f'---\nname: w\ndescription: "D. Use when X."\n{agent_extra}model: inherit # r\n---\n{body}\n'
    )
    rc, out = lint(root)
    assert rc == 0, out
    return out


# ---- P2-2: YAML comment lines in a multi-line tools list ----


def test_comment_line_inside_a_tools_list_does_not_hide_later_tools(tmp_path: Path) -> None:
    extra = "tools:\n  - Read\n  # note\n  - mcp__crm__send_sms\n"
    assert RULE in harness(tmp_path, extra, "Body.")


def test_trailing_comment_cuts_only_its_own_list_item(tmp_path: Path) -> None:
    extra = "tools:\n  - Read # just reading\n  - mcp__crm__send_sms\n"
    assert RULE in harness(tmp_path, extra, "Body.")


def test_commented_out_connector_in_a_list_is_still_scoped(tmp_path: Path) -> None:
    extra = "tools:\n  - Read\n  # - mcp__crm__send_sms\n  - Grep\n"
    assert RULE not in harness(tmp_path, extra, "Body.")


# ---- P2-3: the sender exemption needs a dedicated line ----


@pytest.mark.parametrize(
    "body",
    [
        "The approved list is owned by the orchestrator.",
        "<!-- works from the approved list -->",
        "<!--\nSending worker: makes only the calls on the approved list.\n-->",
        "Not the Sending worker: the approved list is elsewhere.",
        "Notes: Sending worker: works from the approved list.",
    ],
)
def test_a_phrase_or_comment_does_not_make_a_sender(tmp_path: Path, body: str) -> None:
    assert RULE in harness(tmp_path, "tools: Read, mcp__crm__send_sms\n", body)


def test_a_dedicated_sending_worker_line_exempts(tmp_path: Path) -> None:
    assert RULE not in harness(tmp_path, "tools: Read, mcp__crm__send_sms\n", f"Intro.\n{SENDER}")


def test_a_bulleted_sending_worker_line_exempts(tmp_path: Path) -> None:
    assert RULE not in harness(tmp_path, "tools: mcp__crm__send_sms\n", f"- {SENDER}")


def test_a_negated_sending_worker_line_does_not_exempt(tmp_path: Path) -> None:
    body = "Sending worker: not this one, it never works from the approved list."
    assert RULE in harness(tmp_path, "tools: mcp__crm__send_sms\n", body)


# ---- P2-4: the read-only exemption needs a verb-only tool name and a read-only line ----


@pytest.mark.parametrize(
    "tool",
    [
        "mcp__crm__get_and_update_contact",
        "mcp__crm__find_and_delete",
        "mcp__crm__list_then_post",
        "mcp__crm__get*",
        "mcp__crm__get_loan*",
        "mcp__crm__search_and_send_sms",
        "mcp__crm__get_set_flag",
    ],
)
def test_a_compound_or_wildcard_tool_is_not_read_only(tmp_path: Path, tool: str) -> None:
    assert RULE in harness(tmp_path, f"tools: Read, {tool}\n", "This worker is read-only.")


def test_research_alone_does_not_make_a_worker_read_only(tmp_path: Path) -> None:
    assert RULE in harness(tmp_path, "tools: Read, mcp__crm__search\n", "Does research.")


@pytest.mark.parametrize(
    "tool", ["mcp__crm__search", "mcp__crm__get_loan", "mcp__crm__list_loan_statuses"]
)
def test_a_verb_only_read_tool_with_a_read_only_line_is_clean(tmp_path: Path, tool: str) -> None:
    assert RULE not in harness(
        tmp_path, f"tools: Read, {tool}\n", "This worker is read-only research."
    )


# ---- P2-5: heading variants for send-implicit and for `asks` ----


def implicit(root: Path, heading: str, nested: bool = False) -> str:
    skill = root / "skills" / ("outer/inner" if nested else "orch")
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(
        f'---\nname: {skill.name}\ndescription: "D. Use when X."\n---\n{heading}\n'
    )
    return lint(root)[1]


@pytest.mark.parametrize(
    "heading",
    [
        "## Ask Before an Outside Effect",
        "## ask before an outside effect:",
        "# Ask before an outside effect",
        "### Ask before an outside effect.",
        "## Ask before an outside effect  ",
    ],
)
def test_send_implicit_sees_heading_variants(tmp_path: Path, heading: str) -> None:
    assert IMPLICIT in implicit(tmp_path, heading)


def test_a_deeper_or_different_heading_is_not_the_block(tmp_path: Path) -> None:
    assert IMPLICIT not in implicit(tmp_path, "#### Ask before an outside effect")
    assert IMPLICIT not in implicit(tmp_path / "b", "## Ask before an outside effect today")


def test_asks_comes_from_every_skill_not_only_top_level(tmp_path: Path) -> None:
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "w.md").write_text(
        '---\nname: w\ndescription: "D. Use when X."\ntools: mcp__crm__send_sms\nmodel: inherit # r\n---\nBody.\n'
    )
    top = tmp_path / "skills" / "top"
    top.mkdir(parents=True)
    (top / "SKILL.md").write_text('---\nname: top\ndescription: "D. Use when X."\n---\nPlain.\n')
    nested = top / "refs" / "inner"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text(
        '---\nname: inner\ndescription: "D. Use when X."\n---\n## ASK BEFORE AN OUTSIDE EFFECT:\n'
    )
    assert RULE in lint(tmp_path)[1]


# ---- P2-6 to P2-8: unit_tracker ----


def run(*args: str, stdin: str | None = None) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(TRACKER), *args],
        capture_output=True,
        text=True,
        input=stdin,
        check=False,
    )
    return p.returncode, p.stdout


@pytest.fixture
def job(tmp_path: Path) -> str:
    db = str(tmp_path / "t.db")
    code, out = run(
        "init", db, "--table", "sweep", "--key", "id", "--cols", "d",
        "--done", "done_at", "--seed", "-", stdin="1\n2\n",
    )  # fmt: skip
    assert code == 0, out
    return db


def test_a_numeric_key_is_the_same_unit_as_its_text(job: str) -> None:
    assert run("deadletter", job, "--table", "sweep", "--reason", "x")[0] == 0
    code, out = run("upsert", job, "--table", "sweep", "--row", json.dumps({"id": 1, "d": "x"}))
    assert code == 4 and "dead-lettered" in out
    code, out = run(
        "claim", job, "--table", "sweep", "--worker", "w", "--key", json.dumps({"id": 1})
    )
    assert code == 4 and "dead-lettered" in out
    assert "TOTAL: 2" in run("status", job, "--table", "sweep")[1]


def test_a_numeric_upsert_updates_the_seeded_row_instead_of_adding_one(job: str) -> None:
    assert run("upsert", job, "--table", "sweep", "--row", json.dumps({"id": 1, "d": "x"}))[0] == 0
    out = run("status", job, "--table", "sweep")[1]
    assert "TOTAL: 2" in out
    rows = sqlite3.connect(job).execute("SELECT typeof(id), d FROM sweep ORDER BY rowid").fetchall()
    assert rows == [("text", "x"), ("text", None)]


def test_claim_and_release_accept_either_spelling_of_a_key(job: str) -> None:
    key = json.dumps({"id": 2})
    assert run("claim", job, "--table", "sweep", "--worker", "w", "--key", key)[0] == 0
    assert run("release", job, "--table", "sweep", "--worker", "w", "--key", key)[0] == 0
    assert (
        run("claim", job, "--table", "sweep", "--worker", "w", "--key", json.dumps({"id": "2"}))[0]
        == 0
    )


def test_status_is_not_converged_when_everything_failed(job: str) -> None:
    run("deadletter", job, "--table", "sweep", "--reason", "x")
    out = run("status", job, "--table", "sweep")[1]
    assert "FAILED: 2" in out and "PENDING: 0" in out
    assert "STATE: stopped-with-failures" in out and "STATE: converged" not in out


def test_status_is_converged_only_with_no_failures(job: str) -> None:
    for i in ("1", "2"):
        run("upsert", job, "--table", "sweep", "--row", json.dumps({"id": i, "done_at": "t"}))
    assert "STATE: converged" in run("status", job, "--table", "sweep")[1]


def test_status_is_open_while_units_remain(job: str) -> None:
    assert "STATE: open" in run("status", job, "--table", "sweep")[1]


def _module() -> object:
    spec = importlib.util.spec_from_file_location("unit_tracker_mod2", TRACKER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_holder_check_is_inside_the_write_not_a_separate_read(
    job: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """P2-8: a read of the claim followed by a write leaves a window; the test is one statement."""
    run("claim", job, "--table", "sweep", "--worker", "w1", "--key", json.dumps({"id": "1"}))
    mod = _module()
    seen: list[str] = []
    real_open = mod._open  # type: ignore[attr-defined]

    def traced(db: str, create: bool) -> sqlite3.Connection:
        con = real_open(db, create)
        con.set_trace_callback(seen.append)
        return con

    mod._open = traced  # type: ignore[attr-defined]
    rc = mod.main(  # type: ignore[attr-defined]
        [
            "upsert",
            job,
            "--table",
            "sweep",
            "--row",
            json.dumps({"id": "1", "d": "y"}),
            "--worker",
            "w1",
        ]
    )
    assert rc == 0, capsys.readouterr().out
    reads = [s for s in seen if s.lstrip().upper().startswith("SELECT") and "_claimed_by" in s]
    assert not reads, f"holder test must not be a separate read: {reads}"
    assert any(s.lstrip().upper().startswith("UPDATE") and "_claimed_by" in s for s in seen)


def test_a_worker_that_lost_its_claim_cannot_write(job: str) -> None:
    key = json.dumps({"id": "1"})
    run("claim", job, "--table", "sweep", "--worker", "w1", "--key", key)
    run("release", job, "--table", "sweep", "--worker", "w1", "--key", key)
    row = json.dumps({"id": "1", "d": "late"})
    code, out = run("upsert", job, "--table", "sweep", "--row", row, "--worker", "w1")
    assert code == 2 and "claim" in out
    assert sqlite3.connect(job).execute("SELECT d FROM sweep WHERE id='1'").fetchone() == (None,)


def test_a_dead_unit_is_refused_even_for_its_holder_with_worker(job: str) -> None:
    key = json.dumps({"id": "1"})
    run("claim", job, "--table", "sweep", "--worker", "w1", "--key", key)
    run("deadletter", job, "--table", "sweep", "--reason", "x")
    code, out = run(
        "upsert",
        job,
        "--table",
        "sweep",
        "--row",
        json.dumps({"id": "1", "d": "z"}),
        "--worker",
        "w1",
    )
    assert code == 4 and "dead-lettered" in out


def test_racing_upserts_with_worker_and_release_never_write_without_the_claim(
    tmp_path: Path,
) -> None:
    """P2-8 race: not guaranteed to fail on the old code (the window is tiny); the trace test above is."""
    db = str(tmp_path / "r.db")
    run(
        "init",
        db,
        "--table",
        "sweep",
        "--key",
        "id",
        "--cols",
        "d",
        "--done",
        "done_at",
        "--seed",
        "-",
        stdin="1\n",
    )
    key = json.dumps({"id": "1"})
    assert run("claim", db, "--table", "sweep", "--worker", "w1", "--key", key)[0] == 0

    def upsert_args(i: int) -> list[str]:
        row = json.dumps({"id": "1", "d": f"w{i}"})
        return [
            sys.executable,
            "-B",
            str(TRACKER),
            "upsert",
            db,
            "--table",
            "sweep",
            "--row",
            row,
            "--worker",
            "w1",
        ]

    procs = [subprocess.Popen(upsert_args(i), stdout=subprocess.PIPE, text=True) for i in range(8)]
    rel = subprocess.run(
        [sys.executable, "-B", str(TRACKER), "release", db, "--table", "sweep", "--worker", "w1", "--key", key],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    outs = [p.communicate()[0] for p in procs]
    assert rel.returncode == 0
    assert all(o.startswith(("OK", "REFUSED")) for o in outs), outs
    d = sqlite3.connect(db).execute("SELECT d FROM sweep").fetchone()[0]
    assert d is None or d.startswith("w")


def test_unit_tracker_doc_names_the_new_state() -> None:
    doc = (REPO / "skills/finhub-harness/references/unit-tracker.md").read_text()
    status = next(r for r in doc.splitlines() if r.startswith("| `status DB"))
    assert "stopped-with-failures" in status and "converged" in status


# ---- P2-1 and P2-9: README and the light skill ----


def test_readme_claims_only_what_is_wired() -> None:
    text = (REPO / "README.md").read_text()
    assert "register only `EchoTool`" in text
    assert "The command guard, workspace fence and checkpoints are wired" in text
    assert "`--mode read-only|workspace-write|full-access`" in text
    assert "the Docker engine is a library that no shipped entrypoint wires yet" in text
    assert (
        "command guard, workspace fence, Docker engine, MCP client and permission modes are libraries"
        not in text
    )


def test_light_description_is_at_most_600_characters_and_keeps_its_routing() -> None:
    text = (REPO / "skills/finhub-harness-light/SKILL.md").read_text()
    desc = re.search(r'^description: "(.*)"$', text, re.MULTILINE)
    assert desc, "description line"
    d = desc.group(1)
    assert len(d) <= 600, len(d)
    for phrase in (
        "light harness",
        "quick harness",
        "light mode",
        "run it light",
        "Do NOT use",
        "use finhub-harness",
    ):
        assert phrase in d, phrase
    assert "Sending worker:" in text and "approved list" in text
    assert len(text.encode("utf-8")) <= 8000
