"""C3 proof: secret-shape redaction of tool results and MCP text (synthetic, obviously fake data).

Every fake credential is assembled at runtime so no complete token shape is committed.
"""

import sys
import time
from pathlib import Path
from typing import Any

import pytest

from master_finhub.runtime.fake_llm import ScriptedLLM
from master_finhub.runtime.loop import (
    AgentLoop,
    AssistantMessage,
    LoopSnapshot,
    Message,
    ToolCall,
    ToolSpec,
)
from master_finhub.tools.mcp.client import (
    SECRET_SHAPES,
    McpClient,
    McpError,
    StdioServer,
    redact,
)
from master_finhub.tools.secret_scan import RULES, redact_secrets

FAKE = "FAKE"
AWS = "AKIA" + FAKE * 3 + "0000"
AWS_TEMP = "ASIA" + FAKE * 3 + "0000"
GHP = "ghp_" + FAKE * 9
PAT = "github_pat_" + FAKE * 6
ANT = "sk-ant-" + "FAKE0" * 5
OAI = "sk-proj-" + "FAKE0" * 5
SLACK = "xoxb-" + "0000-FAKEFAKE"
JWT = "eyJ" + FAKE * 3 + "." + FAKE * 2 + "." + FAKE * 2
KEY_BODY = "TUFERVVQLU5PVC1BLUtFWQ"  # base64 of "MADEUP-NOT-A-KEY"
PEM = "-----BEGIN " + "PRIVATE KEY-----\n" + KEY_BODY + "\n-----END PRIVATE KEY-----"
SSH = (
    "-----BEGIN " + "OPENSSH PRIVATE KEY-----\n" + KEY_BODY + "\n-----END OPENSSH PRIVATE KEY-----"
)
PGP = (
    "-----BEGIN "
    + "PGP PRIVATE KEY BLOCK-----\n"
    + KEY_BODY
    + "\n-----END PGP PRIVATE KEY BLOCK-----"
)
BEARER = "FAKE0" * 4
MCPKEY = "FAKE0" * 2

POSITIVES = [
    ("private-key", PEM, KEY_BODY),
    ("private-key", SSH, KEY_BODY),
    ("private-key", PGP, KEY_BODY),
    ("aws-access-key", AWS, AWS),
    ("aws-access-key", AWS_TEMP, AWS_TEMP),
    ("github-token", GHP, GHP),
    ("github-pat", PAT, PAT),
    ("anthropic-key", ANT, ANT),
    ("openai-key", OAI, OAI),
    ("slack-token", SLACK, SLACK),
    ("jwt", JWT, JWT),
]
WRAPS = ["{}", '"{}"', "'{}'", "KEY={}", "key: {}\n", '{{"k": "{}"}}', "start {} end"]


@pytest.mark.parametrize("wrap", WRAPS)
@pytest.mark.parametrize(("rule", "secret", "leak"), POSITIVES)
def test_each_rule_redacts_and_labels(rule: str, secret: str, leak: str, wrap: str) -> None:
    out, labels = redact_secrets(wrap.format(secret))
    assert leak not in out and f"[REDACTED:{rule}]" in out
    assert labels == (rule,)
    assert leak not in "".join(labels)


@pytest.mark.parametrize(
    ("text", "expected", "rule"),
    [
        (
            "Authorization: Bearer " + BEARER,
            "Authorization: Bearer [REDACTED:bearer-token]",
            "bearer-token",
        ),
        (
            "authorization: bearer " + BEARER,
            "authorization: bearer [REDACTED:bearer-token]",
            "bearer-token",
        ),
        ("Bearer " + JWT, "Bearer [REDACTED:bearer-token]", "bearer-token"),
        ("x-mcp-key: " + MCPKEY, "x-mcp-key: [REDACTED:mercury-mcp-key]", "mercury-mcp-key"),
        (
            '"x-mcp-key": "' + MCPKEY + '"',
            '"x-mcp-key": "[REDACTED:mercury-mcp-key]"',
            "mercury-mcp-key",
        ),
    ],
)
def test_header_rules_keep_their_prefix(text: str, expected: str, rule: str) -> None:
    assert redact_secrets(text) == (expected, (rule,))


def test_anthropic_wins_over_openai() -> None:
    assert redact_secrets(ANT)[1] == ("anthropic-key",)


def test_truncated_private_key_is_redacted_to_end() -> None:
    out, labels = redact_secrets("before\n" + PEM.split("\n-----END")[0])
    assert out == "before\n[REDACTED:private-key]" and labels == ("private-key",)


def test_two_private_keys_keep_the_text_between() -> None:
    out, _ = redact_secrets(PEM + "\nmiddle text\n" + PEM)
    assert out == "[REDACTED:private-key]\nmiddle text\n[REDACTED:private-key]"


def test_labels_are_deduplicated_in_table_order() -> None:
    out, labels = redact_secrets(f"{GHP} {AWS} {AWS}")
    assert out.count("[REDACTED:aws-access-key]") == 2
    assert labels == ("aws-access-key", "github-token")


NEGATIVES = [
    "a1b2c3d4e5" * 4,  # 40-hex git SHA
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # sha256
    "123e4567-e89b-12d3-a456-426614174000",  # UUID
    "01ARZ3NDEKTSV4RRFFQ69G5FAV",  # ULID
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
    "data:image/png;base64,QUJDAKIA" + FAKE * 3 + "0000==",  # key shape inside base64
    "-----BEGIN PUBLIC KEY-----\nabc\n-----END PUBLIC KEY-----",
    "-----BEGIN CERTIFICATE-----",
    "task-runner-configuration-2024",
    "sk-component-header-wrapper",
    "xoxo-hugs-and-kisses-forever",
    "Bearer securities are negotiable",
    "bearer instruments",
    "AKIA" + FAKE * 3 + "000",
    "AKIA" + FAKE * 3 + "00000",
    "ghp_" + "A" * 19,
    "eyJhbGciOiJIUzI1NiJ9.payload",
    "x-mcp-key: short",
    "BSB 062-000 account 12345678",
    "[REDACTED]",
]


@pytest.mark.parametrize("text", NEGATIVES)
def test_false_positive_corpus_passes_unchanged(text: str) -> None:
    assert redact_secrets(text) == (text, ())


def test_redaction_is_idempotent() -> None:
    corpus = "\n".join([s for _, s, _ in POSITIVES] + ["Bearer " + BEARER, "x-mcp-key: " + MCPKEY])
    once, labels = redact_secrets(corpus)
    assert len(labels) == len(RULES)
    assert redact_secrets(once) == (once, ())


def test_mcp_redact_chains_to_shape_scan() -> None:
    out = redact(f"value=abcd1234 {AWS} {ANT}", ["abcd1234"])
    assert out == "value=[REDACTED] [REDACTED:aws-access-key] [REDACTED:anthropic-key]"


class _LeakyTool:
    spec = ToolSpec(name="echo", description="returns a fake .env", parameters={}, idempotent=True)

    def __init__(self, mode: str = "ok") -> None:
        self.mode = mode

    def run(self, arguments: dict[str, Any]) -> str:
        if self.mode == "raise":
            raise ValueError(f"cannot parse {AWS}")
        return f"AWS_ACCESS_KEY_ID={AWS}\nGITHUB_TOKEN={GHP}\n"


def _all_text(snaps: list[LoopSnapshot]) -> str:
    return "\n".join(m.content for s in snaps for m in s.messages)


@pytest.mark.parametrize("mode", ["ok", "raise", "guard"])
def test_loop_transcript_never_holds_the_fake_key(mode: str) -> None:
    snaps: list[LoopSnapshot] = []
    guard = (lambda call: f"denied, saw Bearer {BEARER}") if mode == "guard" else None
    loop = AgentLoop(ScriptedLLM(), [_LeakyTool(mode)], guard=guard, checkpoint=snaps.append)
    answer = loop.run("echo show the env file")
    text = _all_text(snaps) + answer
    for leak in (AWS, GHP, BEARER):
        assert leak not in text
    assert "[REDACTED:" in snaps[-1].messages[-2].content


def test_resume_rerun_path_is_redacted() -> None:
    call = ToolCall("call-1", "echo", {"text": "x"})
    snap = LoopSnapshot(1, (Message("user", "echo x"), Message("assistant", "", (call,))))
    snaps: list[LoopSnapshot] = []
    llm_reply = AssistantMessage(content="done")

    class _Done:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            return llm_reply

    AgentLoop(_Done(), [_LeakyTool()], checkpoint=snaps.append).resume(snap, in_flight="rerun")
    assert AWS not in _all_text(snaps) and "[REDACTED:aws-access-key]" in _all_text(snaps)


def test_mcp_known_values_are_replaced_before_shapes() -> None:
    value = "pw-" + AWS  # a configured secret that contains a token shape
    assert redact(f"conn={value}", [value]) == "conn=[REDACTED]"


@pytest.mark.parametrize("glue", ["cl\u00e9{}", "{}\u00e9", "\u5bc6\u94a5{}\u3002"])
@pytest.mark.parametrize(("rule", "secret", "leak"), POSITIVES)
def test_non_ascii_neighbours_do_not_hide_a_key(
    rule: str, secret: str, leak: str, glue: str
) -> None:
    out, labels = redact_secrets(glue.format(secret))
    assert leak not in out and labels == (rule,)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("\u8ba4\u8bc1Bearer " + BEARER, "\u8ba4\u8bc1Bearer [REDACTED:bearer-token]"),
        ("\u5bc6\u94a5x-mcp-key: " + MCPKEY, "\u5bc6\u94a5x-mcp-key: [REDACTED:mercury-mcp-key]"),
        ("Bearer\t" + BEARER, "Bearer\t[REDACTED:bearer-token]"),
        ("Bearer\n" + BEARER, "Bearer\n[REDACTED:bearer-token]"),
        ('Bearer "' + BEARER + '"', 'Bearer "[REDACTED:bearer-token]"'),
        ("Bearer " + "F" * 16, "Bearer [REDACTED:bearer-token]"),
        ("Bearer " + "F" * 15, "Bearer " + "F" * 15),
        ("x-mcp-key=" + MCPKEY, "x-mcp-key=[REDACTED:mercury-mcp-key]"),
        ("X-MCP-KEY: " + MCPKEY, "X-MCP-KEY: [REDACTED:mercury-mcp-key]"),
        ("x-mcp-key: " + "F" * 8, "x-mcp-key: [REDACTED:mercury-mcp-key]"),
        ("x-mcp-key: " + "F" * 7, "x-mcp-key: " + "F" * 7),
        ("ghp_" + "F" * 20, "[REDACTED:github-token]"),
        ("github_pat_" + "F" * 20, "[REDACTED:github-pat]"),
        ("github_pat_" + "F" * 19, "github_pat_" + "F" * 19),
        ("sk-ant-" + "F" * 20, "[REDACTED:anthropic-key]"),
        ("sk-ant-" + "F" * 19, "sk-ant-" + "F" * 19),
        ("sk-" + "F0" * 10, "[REDACTED:openai-key]"),
        ("sk-" + "F0" * 9 + "F", "sk-" + "F0" * 9 + "F"),
        ("xoxb-" + "0000-FAKEF", "[REDACTED:slack-token]"),
        ("xoxb-" + "0000-FAKE", "xoxb-" + "0000-FAKE"),
        ("eyJ" + "F" * 10 + ".FAKEF.FAKEF", "[REDACTED:jwt]"),
        ("eyJ" + "F" * 9 + ".FAKEF.FAKEF", "eyJ" + "F" * 9 + ".FAKEF.FAKEF"),
        ("abc" + GHP, "abc" + GHP),  # glued to an ASCII word: not anchored (Does not cover #5)
        ("x" + SLACK, "x" + SLACK),
        ("x" + JWT, "x" + JWT),
        ("-" + JWT, "-" + JWT),  # R10 look-behind: a dash-glued JWT is not anchored (#5)
        ("_" + JWT, "_" + JWT),  # N13: look-behind keeps "_"
        ("0" + JWT, "0" + JWT),  # N13: look-behind keeps digits
        ("." + JWT, ".[REDACTED:jwt]"),
        # a bare header in prose wipes the rest (Does not cover #11): pinned, deliberate
        ("see -----BEGIN " + "PRIVATE KEY----- here\nmore", "see [REDACTED:private-key]"),
    ],
)
def test_lengths_contexts_and_anchors_are_pinned(text: str, expected: str) -> None:
    assert redact_secrets(text)[0] == expected


ADVERSARIAL = [
    "sk-",
    "sk-ant-",
    "sk-abc-",
    "Bearer ",
    "x-mcp-key: ",
    "AKIA",
    "ghp_",
    "github_pat_",
    "xoxb-",
    "eyJ",
    "eyJaaaaaaaaaaa.",
    "eyJ-",
    "eyJ_",
    "eyJ0",
    "eyJaaaaaaaaaaaa-",
    # winners of the self-glued sweep (worst unit per rule at 1 MB)
    "-----BEGIN " + "PRIVATE KEY-----+",
    "Bearer\t" + "a" * 16 + "\n",
    'x-mcp-key="',
    'AKIA"',
    "ghp_" + "a" * 20 + "\n",
    "github_pat_" + "a" * 20 + "'",
    "sk-ant-" + "a" * 20 + "+",
    "sk-proj-" + "0" * 19 + "/",
    "xoxp-" + "a" * 10 + ":",
    "eyJ" + "a" * 10 + '.000000000"',
    "-----BEGIN ",
    "-----BEGIN " + "PRIVATE KEY-----",
]


@pytest.mark.parametrize("unit", ADVERSARIAL)
def test_adversarial_megabyte_stays_fast(unit: str) -> None:
    text = unit * (1_000_000 // len(unit))
    started = time.perf_counter()
    redact_secrets(text)
    assert time.perf_counter() - started < 2.0  # linear: well under 0.3 s; quadratic: minutes
    started = time.perf_counter()
    redact(text, ["aaaa", "0000"], mcp_shapes=False)  # the merged-span path of a successful result
    assert time.perf_counter() - started < 2.0


MCP_ADVERSARIAL = [*ADVERSARIAL[9:15], "eyJ.eyJ.eyJ.", "eyJaaaaa."]  # the eyJ family


@pytest.mark.parametrize("known", [[], ["aaaa"]], ids=["no-known", "fragmenting-known"])
@pytest.mark.parametrize("unit", MCP_ADVERSARIAL)
def test_mcp_error_path_is_linear_on_jwt_shaped_runs(unit: str, known: list[str]) -> None:
    # F1: SECRET_SHAPES' JWT branch had no leading boundary (quadratic: hours at 4 MB).
    text = unit * (4_000_000 // len(unit))
    started = time.perf_counter()
    redact(text, known, mcp_shapes=True)
    assert time.perf_counter() - started < 3.0  # linear: ~1 s or less; quadratic: minutes


@pytest.mark.parametrize(
    "wrap", ["x={}", "a: {}", " {}", "{}", '"{}"', '{{"t":"{}"}}', "{} end", "'{}'", "k={}x"]
)
def test_mcp_error_text_jwt_is_still_redacted(wrap: str) -> None:
    out = redact(wrap.format(JWT), [], mcp_shapes=True)
    assert JWT not in out and "FAKEFAKE" not in out and "[REDACTED" in out


@pytest.mark.parametrize("glue", ["-", "_", "0", "a", "Z"])
def test_mcp_jwt_glued_after_a_segment_character_is_not_matched(glue: str) -> None:
    # Pins F1: the look-behind means a JWT glued after [A-Za-z0-9_-] starts no match
    # (end-to-end result of redact(); the secret_scan table has the same boundary).
    assert redact(glue + JWT, [], mcp_shapes=True) == glue + JWT


@pytest.mark.parametrize("sep", [",", ";"])
def test_bearer_token_stops_at_comma_and_semicolon(sep: str) -> None:  # F2 (R14, R15)
    text = "Bearer " + BEARER + sep + "rest"
    assert redact_secrets(text)[0] == "Bearer [REDACTED:bearer-token]" + sep + "rest"


def test_jwt_at_segment_minimum_is_redacted_by_shapes_alone() -> None:
    # QA M10/M12/M14/M16: segment 1 has 5 chars (< secret_scan R10's 10), so only SECRET_SHAPES
    # can redact it; the fixture JWT hides this because the table's jwt rule covers it too.
    jwt = "eyJ" + "abcde" + "." + "fghij" + "." + "klmno"
    assert redact("e: " + jwt, [], mcp_shapes=True) == "e: [REDACTED]"
    assert SECRET_SHAPES.sub("#", "e: " + jwt) == "e: #"


@pytest.mark.parametrize("glued", ["xghp_" + "a" * 20, "xghs_" + "a" * 20])
def test_glued_github_prefix_is_matched_by_shapes_only(glued: str) -> None:  # QA M25, M28
    assert redact("e: " + glued, [], mcp_shapes=True) == "e: x[REDACTED]"


def test_glued_pat_and_slack_prefix_are_matched_by_shapes_only() -> None:  # QA M26, M27
    assert redact("e: x" + "github_pat_" + "a" * 20, [], mcp_shapes=True) == "e: x[REDACTED]"
    assert redact("e: x" + "xoxb-" + "1" * 10, [], mcp_shapes=True) == "e: x[REDACTED]"


def test_fragmenting_known_value_is_applied_with_shapes() -> None:  # QA T4
    unit = "eyJ" + "a" * 12 + "-"
    frag = "eyJ[REDACTED][REDACTED][REDACTED]-"  # 12 a's = three known "aaaa"; no JWT shape here
    assert redact(unit * 3, ["aaaa"], mcp_shapes=True) == frag * 3
    assert redact(unit * 3, [], mcp_shapes=True) == unit * 3


def test_is_error_result_gets_the_shape_pass_through_the_call_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # QA M21
    monkeypatch.setattr(McpClient, "_secrets", lambda self: [])  # no known values: shapes only
    stub = str(Path(__file__).with_name("mcp_stub_server.py"))
    leak = "denied: Bearer abc123"  # shorter than the table's 16, so only SECRET_SHAPES sees it
    env = {"MCP_STUB_SECRET": leak}
    with McpClient(StdioServer(name="stub", command=(sys.executable, stub), env=env)) as c:
        assert c.call_tool("echo", {"text": leak}).text == leak  # success: no shape pass
        res = c.call_tool("fail", {})
        assert res.is_error and res.text == "boom denied: [REDACTED]"


def test_mcp_values_and_shapes_are_merged_on_the_original_text() -> None:
    assert redact("id=" + AWS, ["0000"]) == "id=[REDACTED:aws-access-key]"
    assert redact("k=sk-ant-" + "abcde8080fghij" * 3, ["8080"]) == "k=[REDACTED:anthropic-key]"
    assert redact(GHP, ["ghp_FAKE"]) == "[REDACTED]"
    assert redact("v=ab+cd/ef==(x) end", ["ab+cd/ef==(x)"]) == "v=[REDACTED] end"  # re.escape


def test_touching_spans_stay_separate_and_overlaps_merge() -> None:
    assert redact(AWS + "-post", ["-post"]) == "[REDACTED:aws-access-key][REDACTED]"
    assert redact(AWS + "-post", ["0-po"]) == "[REDACTED:aws-access-key]st"


def test_successful_mcp_result_gets_the_known_value_pass() -> None:
    stub = str(Path(__file__).with_name("mcp_stub_server.py"))
    value = "stub-secret-value-1"
    cfg = StdioServer(name="stub", command=(sys.executable, stub), env={"MCP_STUB_SECRET": value})
    with McpClient(cfg) as c:
        assert c.call_tool("echo", {"text": f"token={value}"}).text == "token=[REDACTED]"
        assert c.call_tool("echo", {"text": AWS}).text == "[REDACTED:aws-access-key]"
        prose = "Bearer securities are negotiable"
        assert c.call_tool("echo", {"text": prose}).text == prose


def test_non_text_tool_result_fails_closed() -> None:
    class _IntTool:
        spec = ToolSpec(name="echo", description="returns an int", parameters={})

        def run(self, arguments: dict[str, Any]) -> str:
            return 7  # type: ignore[return-value]

    with pytest.raises(TypeError):
        AgentLoop(ScriptedLLM(), [_IntTool()]).run("echo x")


# --- QA round: every character class, prefix letter and minimum length is pinned (D1-D10) ---
F0 = FAKE + "0"


@pytest.mark.parametrize("letter", "abprs")
def test_slack_prefix_letters_each_redacted(letter: str) -> None:  # D1
    assert redact_secrets("xox" + letter + "-" + "0000-FAKEFAKE") == (
        "[REDACTED:slack-token]",
        ("slack-token",),
    )


@pytest.mark.parametrize("letter", "pousr")
def test_github_prefix_letters_and_underscore_body(letter: str) -> None:  # D2, D3
    plain = "gh" + letter + "_" + FAKE * 9
    glued = "gh" + letter + "_" + FAKE * 3 + "_" + FAKE * 3
    assert redact_secrets(plain)[0] == "[REDACTED:github-token]"
    assert redact_secrets(glued)[0] == "[REDACTED:github-token]"


def test_fine_grained_pat_with_underscore_body() -> None:  # D3
    pat = "github_pat_" + FAKE * 5 + "_" + FAKE * 10
    assert redact_secrets("t=" + pat)[0] == "t=[REDACTED:github-pat]"


def test_jwt_dash_and_underscore_in_every_segment() -> None:  # D4
    jwt = "eyJ" + "FAKE-FAKE_FAKE" + "." + "FAKE-_FAKE" + "." + "FAKE_-FAKE"
    assert redact_secrets(jwt) == ("[REDACTED:jwt]", ("jwt",))
    assert redact_secrets("a " + jwt + " b")[0] == "a [REDACTED:jwt] b"


@pytest.mark.parametrize(
    ("seg2", "seg3", "hit"),
    [
        ("FAKEF", "FAKEF", True),
        ("FAKE", "FAKEF", False),  # second segment 4 characters: not a JWT
        ("FAKEF", "FAKE", False),  # third segment 4 characters: not a JWT
    ],
)
def test_jwt_second_and_third_segment_minimum_is_five(
    seg2: str, seg3: str, hit: bool
) -> None:  # D5
    text = "eyJ" + "F" * 10 + "." + seg2 + "." + seg3
    assert (redact_secrets(text)[0] == "[REDACTED:jwt]") is hit
    assert hit or redact_secrets(text)[0] == text


@pytest.mark.parametrize("ch", list("+/~-=."))
def test_header_token_class_covers_each_punctuation(ch: str) -> None:  # D6
    bearer = "Bearer " + F0 + F0 + ch + F0 + F0
    mcp = "x-mcp-key: " + F0 + ch + F0
    assert redact_secrets(bearer) == ("Bearer [REDACTED:bearer-token]", ("bearer-token",))
    assert redact_secrets(mcp) == ("x-mcp-key: [REDACTED:mercury-mcp-key]", ("mercury-mcp-key",))


@pytest.mark.parametrize("tail", [FAKE * 3 + "-" + FAKE * 3, "FAKE0-FAKE0_FAKE0-FAKE0"])
def test_anthropic_dashed_key_keeps_its_own_label(tail: str) -> None:  # D7
    assert redact_secrets("sk-ant-api-" + tail) == ("[REDACTED:anthropic-key]", ("anthropic-key",))
    assert redact_secrets("sk-ant-api03-" + tail)[0] == "[REDACTED:anthropic-key]"


def test_openai_digit_requirement_accepts_any_digit_and_rejects_none() -> None:  # D8
    for digit in "0123456789":
        assert redact_secrets("sk-" + "F" * 19 + digit)[0] == "[REDACTED:openai-key]"
    assert redact_secrets("sk-" + "F" * 20) == ("sk-" + "F" * 20, ())


@pytest.mark.parametrize(
    "text",
    [
        "class BearerAuthenticationHandler(Base):",
        "BearerTokenValidatorFactory",
        "x BearerAuthenticationSchemeProvider y",
    ],
)
def test_bearer_glued_to_an_identifier_is_not_a_header(text: str) -> None:  # D9
    assert redact_secrets(text) == (text, ())


def test_value_and_table_span_with_equal_extent_is_named_by_the_value() -> None:  # D10
    assert redact(AWS, [AWS]) == "[REDACTED]"
    assert redact("k=" + AWS + "!", [AWS]) == "k=[REDACTED]!"


# --- QA round 2: quote and whitespace forms, glued prefixes, near-miss shapes, call-site depth ---
def test_jwt_trailing_dash_stays_outside_the_span() -> None:
    assert redact_secrets(JWT + "-")[0] == "[REDACTED:jwt]-"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Bearer '" + BEARER + "'", "Bearer '[REDACTED:bearer-token]'"),
        ("x-mcp-key': " + MCPKEY, "x-mcp-key': [REDACTED:mercury-mcp-key]"),
        ("x-mcp-key:\t" + MCPKEY, "x-mcp-key:\t[REDACTED:mercury-mcp-key]"),
        ("x-mcp-key:\n" + MCPKEY, "x-mcp-key:\n[REDACTED:mercury-mcp-key]"),
        ("x-mcp-key\t=\t" + MCPKEY, "x-mcp-key\t=\t[REDACTED:mercury-mcp-key]"),
    ],
)
def test_quote_and_whitespace_forms_of_headers(text: str, expected: str) -> None:
    assert redact_secrets(text)[0] == expected


@pytest.mark.parametrize(
    "text",
    [
        "AuthBearer " + BEARER,
        "myx-mcp-key: " + MCPKEY,
        "my_" + PAT,
        "x_" + ANT,
        "AIDA" + FAKE * 3 + "0000",
        "AKIA" + "fake" * 4,
        "eyJ" + "F" * 10 + ".FAKEF!FAKEF",
        "eyJ" + "F" * 10 + "!FAKEF.FAKEF",
        "eyj" + "F" * 10 + ".FAKEF.FAKEF",
    ],
)
def test_glued_prefixes_and_near_miss_shapes_pass_unchanged(text: str) -> None:
    assert redact_secrets(text) == (text, ())


def test_unterminated_private_key_with_trailing_newline_leaves_nothing() -> None:
    text = "before\n" + PEM.split("\n-----END")[0] + "\n"
    assert redact_secrets(text)[0] == "before\n[REDACTED:private-key]"  # R1 uses \Z, not $


def test_mcp_known_value_minimum_is_four_characters() -> None:
    assert redact("password abc here", ["abc"]) == "password abc here"
    assert redact("password abcd here", ["abcd"]) == "password [REDACTED] here"


def test_value_prefix_inside_a_token_span_merges_and_is_named_by_the_value() -> None:
    assert redact(AWS, [AWS[:8]]) == "[REDACTED]"


class _LongTool:
    spec = ToolSpec(name="echo", description="long output", parameters={}, idempotent=True)

    def __init__(self, pad: int) -> None:
        self.pad = pad

    def run(self, arguments: dict[str, Any]) -> str:
        return "x" * self.pad + " AWS_ACCESS_KEY_ID=" + AWS + " tail"


@pytest.mark.parametrize("pad", [5_000, 10_000])
def test_secret_late_in_a_long_result_is_redacted_on_both_paths(pad: int) -> None:
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(ScriptedLLM(), [_LongTool(pad)], checkpoint=snaps.append)
    loop.run("echo show")
    assert AWS not in _all_text(snaps) and "[REDACTED:aws-access-key]" in _all_text(snaps)

    call = ToolCall("call-1", "echo", {"text": "x"})
    snap = LoopSnapshot(1, (Message("user", "echo x"), Message("assistant", "", (call,))))
    resumed: list[LoopSnapshot] = []

    class _Done:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
            return AssistantMessage(content="done")

    AgentLoop(_Done(), [_LongTool(pad)], checkpoint=resumed.append).resume(snap, in_flight="rerun")
    assert AWS not in _all_text(resumed) and "[REDACTED:aws-access-key]" in _all_text(resumed)


# --- QA round 3: upper bounds, header variants, whitespace, long inputs, call sites ---
@pytest.mark.parametrize("variant", ["", "ENCRYPTED ", "RSA ", "EC ", "DSA ", "OPENSSH "])
@pytest.mark.parametrize("body", [100, 3000, 10_000])
def test_private_key_header_variants_and_long_bodies(variant: str, body: int) -> None:
    key = "-----BEGIN " + variant + "PRIVATE KEY-----\n" + "A" * body
    key += "\n-----END " + variant + "PRIVATE KEY-----"
    assert redact_secrets("a\n" + key + "\nb")[0] == "a\n[REDACTED:private-key]\nb"


@pytest.mark.parametrize("ws", ["\r", "\f", "\v", "\r\n", "\t", "\n", "  "])
def test_every_whitespace_after_a_header_name(ws: str) -> None:
    assert redact_secrets("Bearer" + ws + BEARER)[0] == "Bearer" + ws + "[REDACTED:bearer-token]"
    mcp = "x-mcp-key:" + ws + MCPKEY
    assert redact_secrets(mcp)[0] == "x-mcp-key:" + ws + "[REDACTED:mercury-mcp-key]"


@pytest.mark.parametrize("n", [20, 60, 1000])
def test_long_tokens_are_redacted_whole(n: int) -> None:
    cases = [
        ("Bearer " + "FAKE0" * n, "Bearer [REDACTED:bearer-token]"),
        ("x-mcp-key: " + "FAKE0" * n, "x-mcp-key: [REDACTED:mercury-mcp-key]"),
        ("ghp_" + FAKE * 3 * n, "[REDACTED:github-token]"),
        ("github_pat_" + FAKE * 3 * n, "[REDACTED:github-pat]"),
        ("sk-ant-" + "FAKE0" * n, "[REDACTED:anthropic-key]"),
        ("sk-" + "FAKE0" * n, "[REDACTED:openai-key]"),
        ("xox" + "b-" + "0000-FAKE" * n, "[REDACTED:slack-token]"),
        ("eyJ" + "F" * 4 * n + ".FAKEF.FAKEF", "[REDACTED:jwt]"),
        ("eyJ" + "F" * 10 + "." + "F" * 4 * n + ".FAKEF", "[REDACTED:jwt]"),
        ("eyJ" + "F" * 10 + ".FAKEF." + "F" * 4 * n, "[REDACTED:jwt]"),
    ]
    for text, expected in cases:
        assert redact_secrets(text)[0] == expected


def test_digit_free_aws_and_slack_keys_are_redacted() -> None:
    assert redact_secrets("AKIA" + "ABCDEFGHIJKLMNOP")[0] == "[REDACTED:aws-access-key]"
    assert redact_secrets("xox" + "b-" + "ABCDEFGHIJKL")[0] == "[REDACTED:slack-token]"


def test_secret_after_a_long_prefix_is_found_by_both_scanners() -> None:
    text = "x " * 60_000 + AWS
    assert AWS not in redact_secrets(text)[0]
    assert AWS not in redact(text, [])
    assert AWS not in redact(text, [], mcp_shapes=False)


def test_every_known_value_and_every_occurrence_is_redacted() -> None:
    assert (
        redact("a=secretone b=secrettwo", ["secretone", "secrettwo"]) == "a=[REDACTED] b=[REDACTED]"
    )
    assert redact("a=secretone b=secretone", ["secretone"]) == "a=[REDACTED] b=[REDACTED]"
    both = redact("secretone secrettwo secretone", ["secretone", "secrettwo"])
    assert both == "[REDACTED] [REDACTED] [REDACTED]"


class _CallSequenceLLM:
    """Issues two echo calls in one turn, then one more in a second turn, then answers."""

    def __init__(self) -> None:
        self.turn = 0

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> AssistantMessage:
        self.turn += 1
        if self.turn == 1:
            calls = [ToolCall("c1", "echo", {}), ToolCall("c2", "echo", {})]
            return AssistantMessage(content="", tool_calls=calls)
        if self.turn == 2:
            return AssistantMessage(content="", tool_calls=[ToolCall("c3", "echo", {})])
        return AssistantMessage(content="done")


def test_every_tool_call_in_a_loop_is_redacted_not_only_the_first() -> None:
    snaps: list[LoopSnapshot] = []
    loop = AgentLoop(_CallSequenceLLM(), [_LeakyTool()], checkpoint=snaps.append)
    loop.run("go")
    tool_msgs = [m for m in snaps[-1].messages if m.role == "tool"]
    assert len(tool_msgs) == 3
    assert all(AWS not in m.content and "[REDACTED:aws-access-key]" in m.content for m in tool_msgs)


_STUB = """
import json, os, sys
V = os.environ["STUB_VALUE"]
for line in sys.stdin:
    m = json.loads(line)
    i, method = m.get("id"), m.get("method")
    if method == "initialize":
        r = {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {"name": "s"}}
        print(json.dumps({"jsonrpc": "2.0", "id": i, "result": r}), flush=True)
    elif method == "tools/call":
        sys.stderr.write("log " + V + " " + %(aws)r + "\\n")
        sys.stderr.flush()
        err = {"code": -1, "message": "bad " + V + " " + %(aws)r}
        print(json.dumps({"jsonrpc": "2.0", "id": i, "error": err}), flush=True)
"""
VALUE = "hunter2-value"


def test_mcp_error_message_and_stderr_tail_are_redacted_end_to_end(tmp_path: Path) -> None:
    script = tmp_path / "stub.py"
    script.write_text(_STUB % {"aws": AWS}, encoding="utf-8")
    cfg = StdioServer(name="s", command=(sys.executable, str(script)), env={"STUB_VALUE": VALUE})
    with McpClient(cfg) as c:
        with pytest.raises(McpError) as excinfo:
            c.call_tool("echo", {})
        assert "bad" in str(excinfo.value)
        assert VALUE not in str(excinfo.value) and AWS not in str(excinfo.value)
        deadline = time.monotonic() + 10.0  # wait for the reader thread, not a timing assertion
        while not any("log" in x for x in c.stderr_tail) and time.monotonic() < deadline:
            time.sleep(0.02)
        tail = " ".join(c.stderr_tail)
        assert "log" in tail and VALUE not in tail and AWS not in tail


def test_mcp_fail_message_and_stderr_line_are_redacted() -> None:
    c = McpClient(StdioServer(name="s", command=("x",), env={"STUB_VALUE": VALUE}))
    c._stderr.append("log " + VALUE + " " + AWS)
    assert VALUE not in c.stderr_tail[0] and AWS not in c.stderr_tail[0]
    c._fail("died " + VALUE + " " + AWS)
    text = str(c._dead)
    assert "died" in text and VALUE not in text and AWS not in text
