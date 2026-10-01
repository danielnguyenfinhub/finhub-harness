"""Slice 1 CLI proof test."""

import pytest

from master_finhub.cli import main


def test_echo_prompt_prints_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["echo hi"]) == 0
    assert capsys.readouterr().out.strip() == "hi"


def test_unscripted_prompt_fails_clearly(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["do something"]) == 2
    assert "echo" in capsys.readouterr().err


def test_unknown_profile_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--profile", "nope", "x"]) == 2
    err = capsys.readouterr().err
    assert "Why:" in err and "Fix:" in err and "judge" in err


def test_profile_without_key_exit_1_no_network(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["--profile", "miner", "x"]) == 1
    err = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in err and "Fix:" in err
