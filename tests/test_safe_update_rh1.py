"""Proof for RH1: skills/finhub-harness/scripts/safe_update.py, the three-way plan and the staged conflicts.

Each message names the rule (R1-R6 in references/safe-update.md).
adapted from references/repository_harness/crates/harness/src/application/service.rs:516 and :238 (MIT, Hoang Nguyen)
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/finhub-harness/scripts/safe_update.py"
DOC = ROOT / "skills/finhub-harness/references/safe-update.md"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("safe_update", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["safe_update"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = load()
B, L, U = b"base", b"local", b"up"


@pytest.mark.parametrize(
    ("base", "local", "up", "want"),
    [
        (B, B, U, ("update", "unedited locally, upstream changed")),
        (B, L, B, ("keep-local", "edited locally, upstream unchanged")),
        (B, L, L, ("keep", "same text as upstream")),
        (B, L, U, ("conflict", "overlapping-changes")),
        (B, B, None, ("delete", "unedited locally, removed upstream")),
        (B, L, None, ("conflict", "modified-but-removed")),
        (B, None, B, ("keep-local", "removed locally, upstream unchanged")),
        (B, None, U, ("conflict", "missing-managed-file")),
        (B, None, None, ("none", "removed on both sides")),
        (None, None, U, ("create", "new upstream file")),
        (None, L, None, ("preserve", "not installed, not upstream: the user's own file")),
        (None, L, L, ("keep", "same text as upstream")),
        (None, L, U, ("conflict", "existing-unmanaged-path")),
        (None, None, None, ("none", "absent")),
    ],
)
def test_the_fourteen_cases(
    base: bytes | None, local: bytes | None, up: bytes | None, want: tuple[str, str]
) -> None:
    assert mod.decide(base, local, up) == want, f"R1/R2: {base!r} {local!r} {up!r}"


def tree(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def run(*args: str) -> tuple[int, str]:
    p = subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args], capture_output=True, text=True, check=False
    )
    return p.returncode, p.stdout


@pytest.fixture
def trio(tmp_path: Path) -> tuple[Path, Path, Path]:
    base = tree(tmp_path / "base", {"a.md": "1", "b.md": "1", "c.md": "1"})
    local = tree(tmp_path / "local", {"a.md": "1", "b.md": "edited", "c.md": "mine", "own.md": "x"})
    up = tree(tmp_path / "up", {"a.md": "2", "b.md": "1", "c.md": "theirs", "new.md": "n"})
    return base, local, up


def args(t: tuple[Path, Path, Path]) -> list[str]:
    return ["--baseline", str(t[0]), "--local", str(t[1]), "--upstream", str(t[2])]


def test_plan_names_every_path_and_exits_4_on_a_conflict(trio: tuple[Path, Path, Path]) -> None:
    code, out = run("plan", *args(trio))
    assert code == 4, "R3: a conflict is exit 4"
    for line in (
        "PLAN update a.md",
        "PLAN keep-local b.md",
        "PLAN conflict c.md (overlapping-changes)",
        "PLAN preserve own.md",
        "PLAN create new.md",
    ):
        assert line in out, f"R1: the plan must carry {line!r}"
    assert "SUMMARY: 5 path(s), 1 conflict(s)" in out


def test_a_clean_plan_exits_0(tmp_path: Path) -> None:
    t = (
        tree(tmp_path / "b", {"a": "1"}),
        tree(tmp_path / "l", {"a": "1"}),
        tree(tmp_path / "u", {"a": "2"}),
    )
    code, out = run("plan", *args(t))
    assert code == 0 and "PLAN update a" in out, "R3: no conflict is exit 0"


def test_plan_and_stage_never_change_the_local_tree(
    trio: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    snap = {p.name: p.read_text() for p in trio[1].iterdir()}
    run("plan", *args(trio))
    run("stage", *args(trio), "--out", str(tmp_path / "stage"))
    assert {p.name: p.read_text() for p in trio[1].iterdir()} == snap, "R4: live files untouched"


def test_stage_writes_base_local_and_upstream_of_each_conflict_only(
    trio: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    out = tmp_path / "stage"
    assert run("stage", *args(trio), "--out", str(out))[0] == 4
    got = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    assert got == ["c.md/BASE", "c.md/LOCAL", "c.md/UPSTREAM"], "R4: only the conflict is staged"
    assert (out / "c.md/LOCAL").read_text() == "mine"
    assert (out / "c.md/UPSTREAM").read_text() == "theirs"


def test_stage_inside_the_local_tree_is_refused(trio: tuple[Path, Path, Path]) -> None:
    code, _ = run("stage", *args(trio), "--out", str(trio[1] / "stage"))
    assert code != 0 and not (trio[1] / "stage").exists(), "R4: staging must not write into local"


@pytest.mark.skipif(os.name != "posix", reason="symlinks")
def test_a_symlink_is_an_unsafe_path_conflict(tmp_path: Path) -> None:
    t = (
        tree(tmp_path / "b", {"a": "1"}),
        tree(tmp_path / "l", {"a": "1"}),
        tree(tmp_path / "u", {"a": "2"}),
    )
    (t[1] / "a").unlink()
    (t[1] / "a").symlink_to(tmp_path / "elsewhere")
    code, out = run("plan", *args(t))
    assert code == 4 and "PLAN conflict a (unsafe-path)" in out, "R5: a symlink is never followed"


def test_markers_finds_every_conflict_marker_line(tmp_path: Path) -> None:
    f = tmp_path / "f.md"
    f.write_text("ok\n<<<<<<< LOCAL\nx\n||||||| BASE\ny\n=======\nz\n>>>>>>> UPSTREAM\n")
    code, out = run("markers", str(f))
    assert code == 4 and out.count("MARKER") == 4, "R6: four marker lines"
    f.write_text("fine\n= = =\n")
    assert run("markers", str(f))[0] == 0, "R6: a clean file passes"


def test_reference_carries_the_rules() -> None:
    text = DOC.read_text(encoding="utf-8")
    for needle in ("| R1 |", "| R2 |", "| R3 |", "| R4 |", "| R5 |", "| R6 |", "Does not cover"):
        assert needle in text, f"the reference must carry {needle!r}"
