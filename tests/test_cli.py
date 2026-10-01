"""Slice 1 CLI proof test."""

import pytest

from master_finhub.cli import main


def test_echo_prompt_prints_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["echo hi"]) == 0
    assert capsys.readouterr().out.strip() == "hi"


def test_unscripted_prompt_fails_clearly(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["do something"]) == 2
    assert "echo" in capsys.readouterr().err
