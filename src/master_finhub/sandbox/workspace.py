"""Workspace fence: the agent may only write (and, by default, read) inside its workspace folder.

Ideas adapted (MIT, own code) from deepseek-harness fs-sandbox containment.ts:26-27 and
index.ts (check-at-write, write the checked path, FS_SANDBOX_DENIED code) and crewai
file_writer_tool.py (is_relative_to and != root, resolve errors become denials). Reads are
fenced too, a deliberate departure from deepseek (design A71). Denial messages never echo the
caller's path: only a root-relative path, "[path outside workspace]" or "[rejected path]".

Pipeline for every path: lexical reject (pure string work, no filesystem call) -> resolve ->
containment. Slice 3 is a fence, not a sandbox: see the design's accepted-risks table.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path, PureWindowsPath
from typing import Final, Literal

WORKSPACE_ENV_VAR: Final = "MASTER_FINHUB_WORKSPACE"
DEFAULT_WORKSPACE_ROOT: Final = "/workspace"
SANDBOX_DENIED: Final = "FS_SANDBOX_DENIED"
MAX_PATH_CHARS: Final = 1024
RESERVED: Final = frozenset(
    ["con", "prn", "aux", "nul", "conin$", "conout$", "clock$"]
    + [f"{p}{d}" for p in ("com", "lpt") for d in "0123456789¹²³"]
)
BAD_CHARS: Final = frozenset('<>"|?*')
OUTSIDE: Final = "[path outside workspace]"
REJECTED: Final = "[rejected path]"
Mode = Literal["write", "read"]


class SandboxDenied(PermissionError):
    """A path was refused. The message never contains the caller's path."""

    def __init__(self, display_path: str, reason: str, mode: Mode) -> None:
        self.code = SANDBOX_DENIED
        self.display_path = display_path
        self.reason = reason
        super().__init__(
            f'cannot {mode} "{display_path}": file access denied under workspace-{mode} mode '
            f"({reason})"
        )


def lexical_reject(raw: str, root_drive: str) -> str | None:
    """Return a reason or None. Pure string/PurePath work: never touches the filesystem."""
    if not raw or not raw.strip():
        return "empty path"
    if "\0" in raw:
        return "null byte"
    if len(raw) > MAX_PATH_CHARS:
        return "path too long"
    if raw[:2] in ("\\\\", "//", "\\/", "/\\"):
        return "network or device path"
    if any(ch in BAD_CHARS for ch in raw) or any(ord(ch) < 32 for ch in raw):
        return "invalid character"
    p = PureWindowsPath(raw)
    if p.drive:
        if not p.root:
            return "drive-relative path"
        if p.drive.casefold() != root_drive.casefold():
            return "different drive"
    rest = raw[len(p.drive) :]
    if ":" in rest:
        return "colon in path (alternate data stream)"
    for comp in rest.replace("\\", "/").split("/"):
        if comp in ("", ".", ".."):
            continue
        if comp[-1] in ". ":
            return "component ends with dot or space"
        if comp.split(".")[0].rstrip(" ").casefold() in RESERVED:
            return "reserved device name"
    return None


def _resolve_dir(value: str | os.PathLike[str], source: str) -> Path:
    try:
        resolved = Path(value).resolve(strict=True)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"{source} does not exist. Create it or point to another."
        ) from None
    except (OSError, ValueError, RuntimeError):
        raise FileNotFoundError(f"{source} could not be resolved.") from None
    if not resolved.is_dir():
        raise NotADirectoryError(f"{source} is not a folder.")
    return resolved


class Workspace:
    def __init__(
        self,
        root: str | os.PathLike[str] | None = None,
        *,
        fence_reads: bool = True,
        extra_read_roots: Sequence[str | os.PathLike[str]] = (),
    ) -> None:
        env = os.environ.get(WORKSPACE_ENV_VAR)
        if root is not None:
            self._root = _resolve_dir(root, "the root argument")
        elif env:
            self._root = _resolve_dir(env, f"the {WORKSPACE_ENV_VAR} folder")
        else:
            self._root = _resolve_dir(DEFAULT_WORKSPACE_ROOT, "the default /workspace folder")
        self._fence_reads = fence_reads
        extras = tuple(_resolve_dir(r, "an extra read folder") for r in extra_read_roots)
        self._read_roots = (self._root, *extras)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def read_roots(self) -> tuple[Path, ...]:
        return self._read_roots

    def _check(self, path: str | os.PathLike[str], mode: Mode) -> Path:
        raw = os.fspath(path)
        if not isinstance(raw, str):
            raise SandboxDenied(REJECTED, "path must be text", mode)
        reason = lexical_reject(raw, self._root.drive)
        if reason is not None:
            raise SandboxDenied(REJECTED, reason, mode)
        given = Path(raw)
        candidate = given if given.is_absolute() else self._root / raw
        try:
            resolved = candidate.resolve(strict=False)
        except (OSError, ValueError, RuntimeError) as exc:
            raise SandboxDenied(
                REJECTED, f"could not resolve: {type(exc).__name__}", mode
            ) from None
        if mode == "write":
            ok = resolved.is_relative_to(self._root) and resolved != self._root
        else:
            ok = any(resolved.is_relative_to(r) for r in self._read_roots)
        if not ok:
            inside = resolved.is_relative_to(self._root)
            display = resolved.relative_to(self._root).as_posix() if inside else OUTSIDE
            raise SandboxDenied(display, "outside the allowed folders", mode)
        return resolved

    def check_write(self, path: str | os.PathLike[str]) -> Path:
        return self._check(path, "write")

    def check_read(self, path: str | os.PathLike[str]) -> Path:
        return self._check(path, "read")

    def write_text(
        self, path: str | os.PathLike[str], content: str, encoding: str = "utf-8"
    ) -> Path:
        resolved = self.check_write(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            resolved.write_text(content, encoding=encoding)
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
            with os.fdopen(os.open(resolved, flags, 0o644), "w", encoding=encoding) as fh:
                fh.write(content)
        return resolved

    def read_text(self, path: str | os.PathLike[str], encoding: str = "utf-8") -> str:
        target = self.check_read(path) if self._fence_reads else Path(path)
        return target.read_text(encoding=encoding)
