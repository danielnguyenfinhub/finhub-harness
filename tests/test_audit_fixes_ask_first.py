"""Audit leads 6 and 7: connector tools are scoped to the sending worker; the light skill keeps Ask-first."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LINT = REPO / "skills/finhub-harness/scripts/lint_harness.py"
LIGHT = REPO / "skills/finhub-harness-light/SKILL.md"
STEP = REPO / "skills/finhub-harness/SKILL.md"
PATTERNS = REPO / "skills/finhub-harness/references/team-patterns.md"
TEMPLATE = REPO / "skills/finhub-harness/references/orchestrator-template.md"
ASK = "## Ask before an outside effect"
RULE = "connector-tools-unscoped"


def lint(root: Path) -> tuple[int, str]:
    run = subprocess.run(
        [sys.executable, str(LINT), str(root)], capture_output=True, text=True, check=False
    )
    return run.returncode, run.stdout


def build(root: Path, ask: bool, agents: dict[str, str]) -> tuple[int, str]:
    skill = root / "skills" / "orch"
    skill.mkdir(parents=True)
    body = (ASK + "\n") if ask else "Plain.\n"
    (skill / "SKILL.md").write_text(
        f'---\nname: orch\ndescription: "D. Use when X."\ndisable-model-invocation: true\n---\n{body}'
    )
    (root / "agents").mkdir()
    for name, extra in agents.items():
        (root / "agents" / f"{name}.md").write_text(
            f'---\nname: {name}\ndescription: "D. Use when X."\n{extra}model: sonnet # r\n---\nBody.\n'
        )
    return lint(root)


def test_worker_without_tools_line_warns(tmp_path: Path) -> None:
    rc, out = build(tmp_path, True, {"drafter": ""})
    assert RULE in out and "; fix:" in out and "drafter.md" in out and rc == 0


def test_worker_listing_mcp_tools_warns(tmp_path: Path) -> None:
    _, out = build(tmp_path, True, {"drafter": "tools: Read, mcp__crm__send\n"})
    assert RULE in out


def test_scoped_worker_is_clean(tmp_path: Path) -> None:
    _, out = build(tmp_path, True, {"drafter": "tools: Read, Grep\n"})
    assert RULE not in out


def test_disallowed_connectors_count_as_scoped(tmp_path: Path) -> None:
    _, out = build(tmp_path, True, {"drafter": "disallowedTools: mcp__crm__send\n"})
    assert RULE not in out


def test_sender_is_exempt(tmp_path: Path) -> None:
    build(tmp_path, True, {"drafter": "tools: Read\n"})
    (tmp_path / "agents" / "sender.md").write_text(
        '---\nname: sender\ndescription: "D. Use when X."\ntools: mcp__crm__send\nmodel: sonnet # r\n---\n'
        "Makes only the calls on the approved list.\n"
    )
    _, out = lint(tmp_path)
    assert RULE not in out


def test_harness_without_ask_first_is_not_checked(tmp_path: Path) -> None:
    _, out = build(tmp_path, False, {"drafter": ""})
    assert RULE not in out


def test_light_skill_states_ask_first_and_explicit_only() -> None:
    t = LIGHT.read_text()
    assert "Outside effects" in t and "send, write a record, publish, share or pay" in t
    assert "show every call" in t and "explicit yes" in t
    assert "disable-model-invocation: true" in t
    assert "no `mcp__` tools" in t


def test_builder_guidance_scopes_connector_tools() -> None:
    for p in (STEP, PATTERNS, TEMPLATE):
        assert "mcp__<server>__*" in p.read_text(), p.name
    assert "10. Only the sending worker holds the connector tools." in TEMPLATE.read_text()
    assert "`tools:` allowlist without any `mcp__` tool" in STEP.read_text()
    assert "**Connector tools:**" in PATTERNS.read_text()
