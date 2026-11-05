"""Proof for spilling an oversized tool result to a file (D1, D2, D3, HV4).

adapted from references/deepseek_harness/packages/spill/spill-policy/src/index.ts:190 (MIT) and
references/hive/core/framework/agent_loop/internals/tool_result_handler.py:580 (Apache-2.0)
"""

import os
import stat
from pathlib import Path

import pytest

from master_finhub.runtime.context import CLIP_MARKER, ContextManager, estimate_tokens
from master_finhub.runtime.loop import Message
from master_finhub.runtime.spill import SpillStore

BIG = "HEAD-" + "x" * 20_000 + "-TAIL"
CAP = 500  # tokens


def test_small_result_is_not_spilled(tmp_path: Path) -> None:
    store = SpillStore(tmp_path / "spill")
    assert store.spill("short", CAP) is None
    assert not (tmp_path / "spill").exists() or not list((tmp_path / "spill").iterdir())


def test_large_result_is_saved_whole_and_replaced_by_a_preview(tmp_path: Path) -> None:
    store = SpillStore(tmp_path)
    out = store.spill(BIG, CAP)
    assert out is not None
    files = sorted(tmp_path.glob("spill_*.txt"))
    assert len(files) == 1 and files[0].read_text(encoding="utf-8") == BIG
    assert str(files[0]) in out
    assert "HEAD-" in out and "-TAIL" in out


def test_replacement_never_exceeds_the_cap_notice_included(tmp_path: Path) -> None:
    for cap in (60, 100, 500, 3000):
        out = SpillStore(tmp_path / str(cap)).spill(BIG, cap)
        assert out is None or estimate_tokens(out) <= cap


def test_notice_alone_too_big_keeps_the_original_and_writes_nothing(tmp_path: Path) -> None:
    store = SpillStore(tmp_path)
    assert store.spill(BIG, 5) is None
    assert list(tmp_path.iterdir()) == []


def test_notice_is_plain_prose_not_a_bracket_trailer(tmp_path: Path) -> None:
    out = SpillStore(tmp_path).spill(BIG, CAP)
    assert out is not None
    assert "[Saved" not in out and not out.rstrip().endswith("]")
    assert "saved" in out.lower()


def test_storage_failure_keeps_the_original(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    assert SpillStore(blocker / "spill").spill(BIG, CAP) is None


def test_numbering_resumes_after_a_restart(tmp_path: Path) -> None:
    (tmp_path / "spill_0003.txt").write_text("old")
    SpillStore(tmp_path).spill(BIG, CAP)
    names = sorted(p.name for p in tmp_path.glob("spill_*.txt"))
    assert names == ["spill_0003.txt", "spill_0004.txt"]
    assert (tmp_path / "spill_0003.txt").read_text() == "old"  # never overwritten


def test_two_stores_do_not_overwrite_each_other(tmp_path: Path) -> None:
    SpillStore(tmp_path).spill(BIG, CAP)
    SpillStore(tmp_path).spill(BIG + "2", CAP)
    assert len(list(tmp_path.glob("spill_*.txt"))) == 2


@pytest.mark.skipif(os.name != "posix", reason="POSIX modes")
def test_spill_files_are_private(tmp_path: Path) -> None:
    SpillStore(tmp_path / "d").spill(BIG, CAP)
    f = next((tmp_path / "d").glob("spill_*.txt"))
    assert stat.S_IMODE(f.stat().st_mode) == 0o600
    assert stat.S_IMODE(f.parent.stat().st_mode) == 0o700


def tool_message() -> list[Message]:
    return [Message("user", "task"), Message("tool", BIG, tool_call_id="c1")]


def test_context_manager_spills_when_a_directory_is_set(tmp_path: Path) -> None:
    cm = ContextManager(clip_budget_tokens=CAP, spill_dir=tmp_path)
    out = cm.fit(tool_message())
    assert CLIP_MARKER not in out[1].content
    assert estimate_tokens(out[1].content) <= CAP
    assert next(tmp_path.glob("spill_*.txt")).read_text(encoding="utf-8") == BIG


def test_context_manager_without_a_directory_still_clips() -> None:
    out = ContextManager(clip_budget_tokens=CAP).fit(tool_message())
    assert CLIP_MARKER in out[1].content


def test_context_manager_falls_back_to_clipping_when_storage_fails(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    out = ContextManager(clip_budget_tokens=CAP, spill_dir=blocker / "s").fit(tool_message())
    assert CLIP_MARKER in out[1].content


def test_a_second_fit_does_not_spill_the_same_result_again(tmp_path: Path) -> None:
    cm = ContextManager(clip_budget_tokens=CAP, spill_dir=tmp_path)
    once = cm.fit(tool_message())
    cm.fit(once)
    assert len(list(tmp_path.glob("spill_*.txt"))) == 1


def test_a_replacement_always_carries_a_useful_preview(tmp_path: Path) -> None:
    seen = 0
    for cap in range(30, 200):
        d = tmp_path / f"d{cap}"
        out = SpillStore(d).spill(BIG, cap)
        if out is None:
            continue
        seen += 1
        preview = out[out.index("follow.\n") + len("follow.\n") :]
        assert len(preview) - len("\n...\n") >= 40, cap
    assert seen > 0
