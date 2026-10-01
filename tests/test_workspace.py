"""Slice 3 proof tests: workspace fence (synthetic data only)."""

import os
import sys
from pathlib import Path

import pytest

from master_finhub.sandbox.workspace import SandboxDenied, Workspace, lexical_reject

WIN = sys.platform == "win32"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "ws"
    r.mkdir()
    return r


def test_write_inside_root_lands_at_resolved_path(root: Path) -> None:
    ws = Workspace(root)
    out = ws.write_text("a/b.txt", "x")
    assert out == root.resolve() / "a" / "b.txt"
    assert out.read_text(encoding="utf-8") == "x"


@pytest.mark.parametrize(
    "p",
    [
        "test_file.txt",
        "test_folder/test_file.txt",
        "test_folder/../test_file.txt",
        "test_folder/../test_folder/test_file.txt",
    ],
)
def test_autogpt_accessible_vectors_allowed(root: Path, p: str) -> None:
    assert Workspace(root).check_write(p).is_relative_to(root.resolve())


@pytest.mark.parametrize("p", [".", "test_folder/.."])
def test_root_itself_not_writable(root: Path, p: str) -> None:
    with pytest.raises(SandboxDenied):
        Workspace(root).check_write(p)


@pytest.mark.parametrize(
    "p",
    [
        "..",
        "../test_file.txt",
        "../not_workspace",
        "../not_workspace/test_file.txt",
        "test_folder/../..",
        "test_folder/../../test_file.txt",
        "test_folder/../../not_workspace",
        "test_folder/../../not_workspace/test_file.txt",
        "\0",
        "\0test_file.txt",
        "test_folder/\0",
        "test_folder/\0test_file.txt",
        "/",
        "/test_file.txt",
        "/home",
    ],
)
def test_autogpt_escape_matrix_denied(root: Path, p: str) -> None:
    with pytest.raises(SandboxDenied) as ei:
        Workspace(root).check_write(p)
    assert ei.value.code == "FS_SANDBOX_DENIED"


def test_sibling_prefix_dir_denied(root: Path, tmp_path: Path) -> None:
    ws = Workspace(root)
    for p in ("../ws_evil/x.txt", str(tmp_path / "ws_evil" / "x.txt")):
        with pytest.raises(SandboxDenied):
            ws.check_write(p)


def test_absolute_path_inside_root_allowed(root: Path) -> None:
    ws = Workspace(root)
    assert ws.check_write(str(root / "x.txt")) == root.resolve() / "x.txt"


LEXICAL_REJECTS = [
    "\\\\host\\share\\x.txt",
    "//host/share/x.txt",
    "\\\\?\\C:\\x.txt",
    "\\\\.\\PhysicalDrive0",
    "//?/C:/x",
    "C:foo.txt",
    "Z:\\x.txt",
    "file.txt:stream",
    "a/b.txt:$DATA",
    "CON",
    "COM1.log",
    "nul.txt",
    "a/aux",
    "x.",
    "x ",
    ".. /x",
    "a/b./c",
    "a<b",
    "a|b",
    "a?b",
    "",
    "   ",
    "x" * 1025,
]


@pytest.mark.parametrize("raw", LEXICAL_REJECTS)
def test_lexical_rejects_never_touch_filesystem(
    root: Path, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    ws = Workspace(root)

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("filesystem touched")

    monkeypatch.setattr(Path, "resolve", boom)
    monkeypatch.setattr(os.path, "realpath", boom)
    monkeypatch.setattr(os, "stat", boom)
    monkeypatch.setattr(os, "lstat", boom)
    with pytest.raises(SandboxDenied):
        ws.check_write(raw)
    with pytest.raises(SandboxDenied):
        ws.check_read(raw)


def test_bytes_path_denied(root: Path) -> None:
    with pytest.raises(SandboxDenied):
        Workspace(root).check_write(b"x.txt")  # type: ignore[arg-type]


@pytest.mark.parametrize("raw", ["console.txt", "com10.txt", "a\\b.txt", "../x.txt"])
def test_lexical_accepts_ordinary_names(raw: str) -> None:
    assert lexical_reject(raw, "") is None


def test_symlink_file_escape_denied(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("orig", encoding="utf-8")
    try:
        os.symlink(outside, root / "link")
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here")
    with pytest.raises(SandboxDenied):
        Workspace(root).write_text("link", "pwn")
    assert outside.read_text(encoding="utf-8") == "orig"


def test_symlink_dir_ancestor_escape_denied(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside_dir"
    outside.mkdir()
    try:
        os.symlink(outside, root / "d", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("cannot create symlinks here")
    with pytest.raises(SandboxDenied):
        Workspace(root).write_text("d/x.txt", "pwn")
    assert not (outside / "x.txt").exists()


@pytest.mark.skipif(not WIN, reason="junctions are Windows-only")
def test_junction_dir_ancestor_escape_denied(root: Path, tmp_path: Path) -> None:
    import _winapi

    outside = tmp_path / "outside_dir"
    outside.mkdir()
    (outside / "secret.txt").write_text("s", encoding="utf-8")
    try:
        _winapi.CreateJunction(str(outside), str(root / "j"))
    except OSError:
        pytest.skip("cannot create junctions here")
    ws = Workspace(root)
    with pytest.raises(SandboxDenied):
        ws.write_text("j/x.txt", "pwn")
    with pytest.raises(SandboxDenied):
        ws.read_text("j/secret.txt")
    assert not (outside / "x.txt").exists()


@pytest.mark.skipif(WIN, reason="O_NOFOLLOW is POSIX-only")
def test_posix_write_refuses_final_symlink(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("orig", encoding="utf-8")
    os.symlink(outside, root / "link")
    ws = Workspace(root)
    monkeypatch.setattr(Workspace, "check_write", lambda self, p: root.resolve() / "link")
    with pytest.raises(OSError):
        ws.write_text("link", "pwn")
    assert outside.read_text(encoding="utf-8") == "orig"


def test_reads_outside_root_denied_by_default(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("o", encoding="utf-8")
    with pytest.raises(SandboxDenied) as ei:
        Workspace(root).read_text(str(outside))
    assert "read" in str(ei.value)


def test_extra_read_roots_allow_reads_not_writes(root: Path, tmp_path: Path) -> None:
    ref = tmp_path / "ref"
    ref.mkdir()
    (ref / "a.txt").write_text("r", encoding="utf-8")
    ws = Workspace(root, extra_read_roots=[ref])
    assert ws.read_text(str(ref / "a.txt")) == "r"
    with pytest.raises(SandboxDenied):
        ws.write_text(str(ref / "b.txt"), "x")


def test_fence_reads_false_is_explicit_only(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("o", encoding="utf-8")
    assert Workspace(root, fence_reads=False).read_text(str(outside)) == "o"
    monkeypatch.setenv("MASTER_FINHUB_FENCE_READS", "0")
    with pytest.raises(SandboxDenied):
        Workspace(root).read_text(str(outside))


def test_denials_never_echo_paths(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ws = Workspace(root)
    outside_abs = str(tmp_path / "Clients" / "client_a" / "payslip.pdf")
    msgs = []
    for raw in (outside_abs, "../Clients/client_a/payslip.pdf", "C:foo/client_a.txt"):
        with pytest.raises(SandboxDenied) as ei:
            ws.check_write(raw)
        msgs.append(str(ei.value))

    def bad_resolve(self: Path, strict: bool = False) -> Path:
        raise OSError(2, "x", r"C:\Clients\client_a")

    monkeypatch.setattr(Path, "resolve", bad_resolve)
    with pytest.raises(SandboxDenied) as ei:
        ws.check_write("anything.txt")
    msgs.append(str(ei.value))
    for m in msgs:
        for banned in (str(tmp_path), "client_a", "payslip", "Clients"):
            assert banned not in m
        assert any(ok in m for ok in ("[path outside workspace]", "[rejected path]", "OSError"))


def test_inside_denial_shows_root_relative_path(root: Path) -> None:
    with pytest.raises(SandboxDenied) as ei:
        Workspace(root).check_write(".")
    assert 'cannot write "."' in str(ei.value)
    assert str(root) not in str(ei.value)


def test_root_resolved_once(root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = Workspace(root)
    monkeypatch.chdir(tmp_path)
    assert ws.write_text("x.txt", "1") == root.resolve() / "x.txt"


def test_root_from_env_var(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MASTER_FINHUB_WORKSPACE", str(root))
    assert Workspace().root == root.resolve()


def test_missing_root_raises_without_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError) as ei:
        Workspace(tmp_path / "nope")
    assert str(tmp_path) not in str(ei.value)
    assert "root argument" in str(ei.value)


def test_missing_env_root_names_the_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MASTER_FINHUB_WORKSPACE", str(tmp_path / "nope"))
    with pytest.raises(FileNotFoundError) as ei:
        Workspace()
    assert "MASTER_FINHUB_WORKSPACE" in str(ei.value)
    assert str(tmp_path) not in str(ei.value)


@pytest.mark.skipif(not WIN, reason="Windows paths")
@pytest.mark.parametrize("p", ["..\\..\\x.txt", "test_folder\\..\\..\\x.txt"])
def test_windows_backslash_traversal_denied(root: Path, p: str) -> None:
    with pytest.raises(SandboxDenied):
        Workspace(root).check_write(p)


@pytest.mark.skipif(not WIN, reason="Windows paths")
def test_windows_case_insensitive_containment(root: Path) -> None:
    out = Workspace(root).check_write(str(root).upper() + "\\x.txt")
    assert out.is_relative_to(root.resolve())


@pytest.mark.parametrize("raw", ["a\x00b.txt", "x.txt\x00", "\x00", "dir/\x00/x.txt"])
def test_nul_in_path_denied_for_read_and_write(root: Path, raw: str) -> None:
    ws = Workspace(root)
    with pytest.raises(SandboxDenied):
        ws.check_write(raw)
    with pytest.raises(SandboxDenied):
        ws.check_read(raw)
