"""Slice 4 router proof tests (no network, no SDK needed except where noted)."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import get_args

import pytest

from master_finhub.runtime.router import (
    DEFAULT_PROFILE_TIERS,
    DEFAULT_TIER_MODELS,
    ModelChoice,
    Router,
    RouterConfigError,
    UnknownProfileError,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "master_finhub"


def test_judge_maps_to_opus() -> None:
    assert Router().resolve("judge") == ModelChoice(
        "judge", "anthropic", "opus", "claude-opus-5-5", 8192
    )


def test_miner_maps_to_sonnet() -> None:
    choice = Router().resolve("miner")
    assert (choice.tier, choice.model) == ("sonnet", "claude-sonnet-5-5")


@pytest.mark.parametrize(
    ("profile", "tier"),
    [
        ("judge", "opus"),
        ("strategy-architect", "opus"),
        ("miner", "sonnet"),
        ("builder", "sonnet"),
        ("qa", "sonnet"),
        ("grunt", "haiku"),
    ],
)
def test_all_default_profiles(profile: str, tier: str) -> None:
    assert Router().resolve(profile).tier == tier


def test_tier_override_changes_model_only() -> None:
    router = Router(tier_models={**DEFAULT_TIER_MODELS, "opus": "claude-fable-5-1"})
    assert router.resolve("judge").model == "claude-fable-5-1"
    assert router.resolve("miner").model == "claude-sonnet-5-5"


def test_unknown_profile_three_parts() -> None:
    with pytest.raises(UnknownProfileError) as info:
        Router().resolve("judgee")
    lines = str(info.value).split("\n")
    assert len(lines) == 3
    assert lines[0].startswith("Unknown model profile 'judgee'")
    assert lines[1].startswith("Why:") and lines[2].startswith("Fix:")
    assert "closest: judge" in lines[0]
    assert all(name in lines[1] for name in DEFAULT_PROFILE_TIERS)


def test_unknown_profile_no_close_match_omits_hint() -> None:
    with pytest.raises(UnknownProfileError) as info:
        Router().resolve("zzz")
    assert "closest:" not in str(info.value)


def test_profile_tier_missing_from_table_rejected() -> None:
    with pytest.raises(RouterConfigError) as info:
        Router(tier_models={"opus": "x", "sonnet": "y"})
    assert "haiku" in str(info.value) and "grunt" in str(info.value)


def test_max_tokens_bounds() -> None:
    for bad in (0, 21_334):
        with pytest.raises(RouterConfigError):
            Router(max_tokens=bad)
    assert Router(max_tokens=21_333).resolve("judge").max_tokens == 21_333


def test_router_tables_frozen() -> None:
    profiles = {"x": "opus"}
    router = Router(profiles=profiles)  # type: ignore[arg-type]
    profiles["y"] = "opus"
    with pytest.raises(UnknownProfileError):
        router.resolve("y")
    with pytest.raises(TypeError):
        router.profiles["z"] = "opus"  # type: ignore[index]


def test_model_ids_live_in_one_place() -> None:
    offenders = [
        p.name
        for p in SRC.rglob("*.py")
        if p.name != "router.py" and "claude-" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_default_tier_models_are_in_installed_sdk_model_list() -> None:
    anthropic = pytest.importorskip("anthropic")
    known = set(get_args(get_args(anthropic.types.Model)[0]))
    assert set(DEFAULT_TIER_MODELS.values()) <= known


def test_core_modules_import_without_anthropic_in_subprocess() -> None:
    code = textwrap.dedent("""
        import sys
        sys.modules['anthropic'] = None
        import master_finhub.runtime.router, master_finhub.runtime.loop, master_finhub.cli
        from master_finhub.runtime.router import Router
        from master_finhub.runtime.anthropic_llm import ProviderError
        assert Router().resolve('judge').tier == 'opus'
        try:
            Router().build_llm('judge')
        except ProviderError as exc:
            assert exc.code == 'CONFIG' and 'pip install -e ".[anthropic]"' in str(exc)
            print('OK')
        """)
    env = {**os.environ, "PYTHONPATH": str(SRC.parent)}
    env.pop("ANTHROPIC_API_KEY", None)
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, check=False
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "OK"
