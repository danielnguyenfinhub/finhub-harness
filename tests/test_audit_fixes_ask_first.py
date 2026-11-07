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
    skill.mkdir(parents=True, exist_ok=True)
    body = (ASK + "\n") if ask else "Plain.\n"
    (skill / "SKILL.md").write_text(
        f'---\nname: orch\ndescription: "D. Use when X."\ndisable-model-invocation: true\n---\n{body}'
    )
    (root / "agents").mkdir(exist_ok=True)
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
    _, out = build(tmp_path, True, {"drafter": "disallowedTools: mcp__*\n"})
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


# ---- re-audit: false negatives and false positives of connector-tools-unscoped ----


def body_agent(name: str, extra: str, body: str, desc: str = "D. Use when X.") -> tuple[str, str]:
    return (
        name,
        f'---\nname: {name}\ndescription: "{desc}"\n{extra}model: inherit # r\n---\n{body}\n',
    )


def lint_agents(root: Path, *agents: tuple[str, str]) -> tuple[int, str]:
    build(root, True, {})
    for old in (root / "agents").glob("*.md"):
        old.unlink()
    for name, text in agents:
        (root / "agents" / f"{name}.md").write_text(text)
    return lint(root)


def warned(
    root: Path, name: str, extra: str, body: str = "Body.", desc: str = "D. Use when X."
) -> bool:
    rc, out = lint_agents(root, body_agent(name, extra, body, desc))
    assert rc == 0, out  # WARN only: exit code unchanged
    if RULE in out:
        assert "; fix:" in out
    return RULE in out


def test_negated_mention_of_approved_list_does_not_exempt(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "", "I never send. The approved list is the orchestrator's.")


def test_approved_list_in_description_does_not_exempt(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "", desc="Drafts messages for the approved list.")


def test_approved_list_inside_code_fence_does_not_exempt(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "", "```\nworks from the approved list\n```")


def test_positive_approved_list_in_body_still_exempts(tmp_path: Path) -> None:
    assert not warned(
        tmp_path, "w", "tools: mcp__crm__send\n", "Works only from the approved list."
    )


def test_one_named_disallowed_tool_is_not_scoped(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "disallowedTools: mcp__crm__send\n")
    assert warned(tmp_path, "w2", "disallowedTools: mcp__other__x\n")


def test_catch_all_disallowed_pattern_is_scoped(tmp_path: Path) -> None:
    assert not warned(tmp_path, "w", "disallowedTools: mcp__*\n")


def test_wildcard_tools_value_warns(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", 'tools: "*"\n')
    assert warned(tmp_path, "w2", "tools: *\n")


def test_yaml_comment_mentioning_mcp_does_not_warn(tmp_path: Path) -> None:
    assert not warned(tmp_path, "w", "tools: Read # never mcp__ tools\n")


def test_comment_hiding_nothing_real_mcp_tool_still_warns(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "tools: Read, mcp__crm__send # sends\n")


def test_read_only_research_worker_with_read_style_connector_tools_is_clean(tmp_path: Path) -> None:
    extra = "tools: Read, mcp__crm__search, mcp__crm__get_loan\n"
    assert not warned(tmp_path, "w", extra, "This worker is read-only research.")


def test_read_style_tools_without_a_read_only_body_still_warn(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "tools: Read, mcp__crm__search\n", "Does things.")


def test_read_only_body_with_a_send_tool_still_warns(tmp_path: Path) -> None:
    extra = "tools: Read, mcp__crm__search, mcp__crm__send_sms\n"
    assert warned(tmp_path, "w", extra, "This worker is read-only research.")


def test_read_only_claim_that_is_negated_still_warns(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "tools: mcp__crm__search\n", "This worker is not read-only.")


def test_server_wide_pattern_is_not_read_style(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "tools: mcp__crm__*\n", "Read-only research.")


def test_yaml_list_and_crlf_forms_are_handled(tmp_path: Path) -> None:
    assert warned(tmp_path, "w", "tools:\n  - Read\n  - mcp__crm__send\n")
    assert not warned(tmp_path, "w2", "tools:\n  - Read\n  - Grep\n")


def test_repo_lint_run_is_unchanged() -> None:
    rc, out = lint(REPO / ".claude")
    assert rc == 0 and "0 error" in out and "5 warning" in out, out[-300:]


def test_ask_first_qa_contradiction_is_gone() -> None:
    t = STEP.read_text()
    assert "QA agents get a type with all tools (" not in t
    assert "QA agents get a type with all tools except `mcp__` connector tools" in t
