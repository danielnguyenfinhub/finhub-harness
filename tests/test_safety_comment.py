"""GUARD-COMMENT proof tests: a shell comment ends at the newline and a `#` starts one only at the
start of a word, so the guard judges every command bash would run (synthetic data only)."""

import time

import pytest

from master_finhub.runtime.loop import ToolCall
from master_finhub.tools import safety
from master_finhub.tools.safety import (
    CommandPolicy,
    check_command,
    check_rule,
    command_names,
    guard_tool_call,
    lex,
)

DEL = "r" + "m -rf /"  # built so the dangerous line is not typed whole
KEY = "cat ~/.ssh/id_rsa"
DEL_RULE = "recursive-delete-root"
KEY_RULE = "sensitive-path"


def guard(command: str) -> str | None:
    return guard_tool_call(ToolCall("1", "sh", {"command": command}))


def test_command_after_a_comment_line_is_still_judged() -> None:
    cases = [
        (f"echo hi # note\n{DEL}", DEL_RULE),
        (f"echo hi # note\n{KEY}", KEY_RULE),
        (f"echo hi # note\r\n{DEL}", DEL_RULE),
        (f"echo hi # note\r\n{KEY}", KEY_RULE),
        (f"# first\n# second\n{DEL}", DEL_RULE),
        (f"echo a;# c\n{DEL}", DEL_RULE),
        (f"echo a && # c\n{KEY}", KEY_RULE),
        (f"echo $(true # c\n)\n{DEL}", DEL_RULE),
        (f"files=(\n a # c\n)\n{DEL}", DEL_RULE),
        (f"echo a\t# c\n{DEL}", DEL_RULE),
        (f"ls # don't\n{DEL}", DEL_RULE),
        (f"echo 'a\\' # c\n{DEL}", DEL_RULE),
    ]
    for command, rule in cases:
        got = check_rule(command)
        assert got == rule, f"comment hid a command: {command!r} -> {got!r}"


def test_quote_in_a_comment_cannot_hide_the_next_line() -> None:
    # bash ends the comment at the newline, so the quote is never opened and the delete runs
    for command in (f"echo a #'\n{DEL}\n#'", f'echo a #"\n{KEY}\n#"'):
        got = check_rule(command)
        assert got is not None, f"comment quote hid a command: {command!r}"


def test_backslash_does_not_extend_a_comment() -> None:
    cases = [
        (f"echo hi # c \\\n{DEL}", DEL_RULE),
        (f"echo a \\\n# c\n{DEL}", DEL_RULE),
        (f"echo x\\\n# ;{DEL}", DEL_RULE),  # the continuation makes `x#`: no comment
    ]
    for command, rule in cases:
        got = check_rule(command)
        assert got == rule, f"backslash extended a comment: {command!r} -> {got!r}"


def test_line_continuation_still_joins_words() -> None:
    for command in ("r\\\n" + DEL[1:], DEL[:-1] + "\\\n/", f"echo a \\\n# c\n{DEL}"):
        got = check_rule(command)
        assert got == DEL_RULE, f"continuation no longer joins: {command!r} -> {got!r}"
    # the continuation makes `a #...` here, so the rest of that line is a comment
    got = check_rule(f"echo a \\\n# {KEY}")
    assert got is None, f"continuation no longer joins: a comment was judged, {got!r}"


def test_comment_in_an_ambiguous_place_is_refused() -> None:
    # bash reads these `#` as a comment or as text depending on the construct, so the guard
    # does not guess: it refuses, and no command is hidden
    refused = [
        f"echo `#x`; {DEL}",
        f"echo `echo hi #x`; {KEY}",
        f"echo `true`#x; {DEL}",
        f"echo $(true)#x; {DEL}",
        f"(true)#'\n{DEL}\n)\n#'",
        f"echo ${{x:- #}}; {DEL}",
        f'echo "$(echo "a #b")"; {DEL}',
    ]
    for command in refused:
        got = check_rule(command)
        assert got == "unparseable", f"ambiguous comment was guessed: {command!r} -> {got!r}"


def test_comment_after_a_closed_construct_is_still_a_comment() -> None:
    allowed = [
        "(cd src && make) # build",
        "echo $(date) # now",
        'echo "$(date)" # now',
        "echo `date` # now",
        "echo ${x} # c",
        'echo "${x:-a}" # c',
        'echo "(" # c',
        'echo "a)" # c',
        "f() { :; } # c",
        "x=$(\n  git log  # recent\n)\necho $x",
        "files=(\n  a.py  # first\n  b.py\n)\nls ${files[@]}",
        "(\n  cd src  # go there\n  make\n)",
        "(cd src && make\n# done\n)",
        "f() {\n  # note\n  ls\n}\nf",
        "echo '(' # c",
        "echo '`' # c",
        "echo '${' # c",
    ]
    for command in allowed:
        got = check_rule(command)
        assert got is None, f"closed construct made a comment fatal: {command!r} -> {got!r}"
    got = check_rule(f"echo $(date) # c\n{DEL}")
    assert got == DEL_RULE, f"comment after a closed construct hid a command: {got!r}"


def test_hash_inside_a_word_is_not_a_comment() -> None:
    cases = [
        (f"echo foo#bar; {DEL}", DEL_RULE),
        (f"echo $#; {DEL}", DEL_RULE),
        (f"echo ${{x#a}}; {KEY}", KEY_RULE),
        (f"echo ${{#x}}; {DEL}", DEL_RULE),
        (f"curl http://x/#a; {DEL}", DEL_RULE),
        (f"echo a\\ #b; {DEL}", DEL_RULE),  # an escaped space keeps the word going
        (f"echo a=#b; {DEL}", DEL_RULE),
    ]
    for command, rule in cases:
        got = check_rule(command)
        assert got == rule, f"mid-word hash hid a command: {command!r} -> {got!r}"


def test_shlex_does_not_cut_the_line_at_a_hash() -> None:
    tokens = lex(f"echo a#b; {DEL}", True)
    assert "a#b" in tokens and "rm" in tokens, f"lexer cut at a hash: {tokens!r}"


def test_hash_inside_quotes_is_data() -> None:
    denied = [
        f"echo '#x'; {DEL}",
        f'echo "a #b"; {DEL}',
        f"echo \\#x; {DEL}",
        f'echo "q #r"; {KEY}',
    ]
    for command in denied:
        assert check_rule(command) is not None, f"quoted hash hid a command: {command!r}"
    for command in ("echo '# not a comment'", 'echo "a # b"', "echo '#x' \"#y\""):
        got = check_rule(command)
        assert got is None, f"quoted hash was refused: {command!r} -> {got!r}"


def test_comment_text_is_not_judged_as_commands() -> None:
    allowed = [
        f"echo hi # {KEY}",
        f"echo hi\t# {KEY}",
        f"echo 'a\\' # {KEY}",
        f"echo hi # {DEL}",
        "# just a note",
        "ls # don't",
        'echo ok # say "hi',
        "ls # a\n# b\nls -la",
        "ls # a\r\nls -la",
    ]
    for command in allowed:
        got = check_rule(command)
        assert got is None, f"comment text was judged: {command!r} -> {got!r}"
        assert guard(command) is None, f"guard refused a comment: {command!r}"


def test_plain_hash_words_still_pass() -> None:
    for command in (
        "curl http://x/#a",
        "echo foo#bar",
        "echo $#",
        'git commit -m "fix #12"',
        "git log --grep=#12",
        "ls #",
    ):
        got = check_rule(command)
        assert got is None, f"plain hash word was refused: {command!r} -> {got!r}"


def test_nested_shell_string_keeps_its_own_lines() -> None:
    for command in (f'bash -c "echo a # c\n{DEL}"', f"sh -c 'echo a # c\n{KEY}'"):
        got = check_rule(command)
        assert got in (DEL_RULE, KEY_RULE), f"nested comment hid a command: {command!r} -> {got!r}"


def test_command_names_see_lines_after_a_comment() -> None:
    assert command_names("echo hi # a\nls") == ["echo", "ls"]
    assert command_names("echo a#b; ls") == ["echo", "ls"]
    assert command_names(f"echo hi # {DEL}") == ["echo"]
    policy = CommandPolicy(mode="allowlist", allowed_commands=frozenset({"echo"}))
    denial = check_command("echo hi # a\nls", policy)
    assert denial is not None and "not-allowlisted" in denial, f"allowlist missed ls: {denial!r}"
    assert check_command(f"echo hi # {DEL}", policy) is None


def test_guard_tool_call_denies_each_reported_probe() -> None:
    probes = [
        f"echo hi # note\n{DEL}",
        f"echo hi # note\n{KEY}",
        f"echo foo#bar; {DEL}",
    ]
    for command in probes:
        denial = guard(command)
        assert denial is not None, f"guard let a comment probe through: {command!r}"
        assert "Blocked by safety policy" in denial
    assert guard(DEL) is not None and guard(KEY) is not None


def test_comment_scan_is_linear() -> None:
    text = "echo a # c\n" * 800 + "ls #" * 100
    assert len(text) <= 10_000
    start = time.process_time()
    got = check_rule(text)
    took = time.process_time() - start
    assert got is None, f"comment-heavy text was refused: {got!r}"
    assert took < 1.0, f"superlinear comment scan: {took:.3f}s"


def test_old_denials_are_kept() -> None:
    # HEAD denied each of these; a quote the scanner and bash read differently (an apostrophe in
    # a here-document body or in an ANSI-C string) must not turn a denial into an allow
    cases = [
        f"cat <<EOF\ndon't\nEOF\n{DEL}",
        f"cat > notes.txt <<EOF\nit's done\nEOF\n{DEL}",
        f"git commit -F- <<EOF\nfix: don't crash\nEOF\n{DEL}",
        f"cat <<EOF\nit's\nEOF\n{DEL} ; echo done",
        f"cat <<EOF\nDon't\nEOF\necho ok\n{DEL}",
        f"cat <<EOF\nit's\nEOF\n{DEL} # tail",
        f"echo $'it\\'s'\n{DEL}",
        f"echo $'it\\'s'\n{KEY}",
    ]
    for command in cases:
        got = check_rule(command)
        assert got in (DEL_RULE, KEY_RULE), f"old denial was lost: {command!r} -> {got!r}"
        assert guard(command) is not None, f"guard lost an old denial: {command!r}"


def test_allowlist_keeps_old_names() -> None:
    policy = CommandPolicy(mode="allowlist", allowed_commands=frozenset({"echo"}))
    command = "echo $'it\\'s'\nls"
    assert "ls" in command_names(command), f"old command name was lost: {command_names(command)!r}"
    assert check_command(command, policy) is not None


def test_multi_line_fork_bomb_is_still_caught() -> None:
    # fork_bomb needs `name(){` with the whitespace gone, so _normalise must keep newlines
    # and not turn them into `;`
    for command in (
        "bomb()\n{ bomb|bomb& }; bomb",
        "bomb()\n{\n bomb | bomb &\n}\nbomb",
        "bomb() # c\n{ bomb|bomb& }; bomb",  # HEAD's text keeps the comment between `()` and `{`
    ):
        got = check_rule(command)
        assert got == "fork-bomb", f"multi-line fork bomb got through: {command!r} -> {got!r}"


def test_lex_does_not_rescan_its_input() -> None:
    # the caller prepares the text once; a second scan would delete this backslash-newline
    tokens = lex("a\\\nb", True)
    assert tokens == ["a\nb"], f"lex rescanned its input: {tokens!r}"


def test_legacy_path_is_heads_text() -> None:
    # the union re-runs the guard on HEAD's own text, which keeps comments and cuts at the first `#`
    token = safety._LEGACY.set(True)
    try:
        flat = safety._normalise("echo a # c \\\nb")
        text = safety._lexable("echo 'x\ny' # c\nz")
    finally:
        safety._LEGACY.reset(token)
    assert flat == "echo a # c b", f"legacy path is not HEAD's text: {flat!r}"
    assert text == "echo 'x;y' # c;z", f"legacy path is not HEAD's text: {text!r}"


def test_legacy_rerun_is_skipped_without_hash_or_newline(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []
    real = safety._check_inner

    def spy(command: str, depth: int, sensitive: bool) -> str | None:
        calls.append(safety._LEGACY.get())
        return real(command, depth, sensitive)

    monkeypatch.setattr(safety, "_check_inner", spy)
    check_rule("bash -c " * 3 + "a " * 100)
    assert calls == [False] * len(calls), f"legacy rerun was not skipped: {calls!r}"
    calls.clear()
    check_rule("echo a # c")
    assert calls == [False, True], f"legacy rerun missing for a `#`: {calls!r}"
    calls.clear()
    check_rule("echo a\nls")
    assert calls == [False, True], f"legacy rerun missing for a newline: {calls!r}"


def test_plain_command_is_not_rescanned() -> None:
    # a command with no `#` and no newline comes back as the same object, so the long nested
    # vectors of test_command_scan_cost pay no scan at every level
    command = "bash -c " * 3 + "./a " * 100
    assert safety._scan(command, ";") is command, "plain command was rescanned"
    assert safety._scan(command, "\n") is command, "plain command was rescanned"
