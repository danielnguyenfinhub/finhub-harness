"""File-system helpers for the checkpoint store (split out of dag_engine.py).

Rule for this whole package: no raise happens inside an ``except`` block. ``attempt`` runs a
callable, drops the exception and hands back only its class and errno, so the error raised
afterwards has no ``__context__`` and cannot carry a document or an absolute path.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal, TypeVar

T = TypeVar("T")
Failure = tuple[type[BaseException], int]  # (exception class, errno or 0)

MOVEFILE_WRITE_THROUGH: Final = 0x8  # MOVEFILE_REPLACE_EXISTING (0x1) is deliberately not set
ERROR_ACCESS_DENIED: Final = 5
ERROR_SHARING_VIOLATION: Final = 32
EXISTS_CODES: Final = frozenset({80, 183})  # ERROR_FILE_EXISTS, ERROR_ALREADY_EXISTS
BUSY_CODES: Final = frozenset({ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION})
BUSY_RETRIES: Final = 3
BUSY_BACKOFF_SECONDS: Final = 0.05


def attempt(
    fn: Callable[[], T], catch: tuple[type[BaseException], ...]
) -> tuple[T | None, Failure | None]:
    """Run fn. On a caught error return (None, (class, errno)); the instance is dropped."""
    try:
        return fn(), None
    except catch as exc:
        return None, (type(exc), getattr(exc, "errno", None) or 0)


@dataclass(frozen=True)
class PublishFailure:
    kind: Literal["exists", "busy", "unsafe"]
    code: int = 0


def _move_file_ex(src: str, dst: str, flags: int) -> int:
    """Windows MoveFileExW via stdlib ctypes. Returns 0 on success, else GetLastError()."""

    def call() -> int:
        if sys.platform != "win32":  # also lets mypy skip the Windows-only ctypes API on Linux
            raise OSError("MoveFileExW exists only on Windows")
        import ctypes
        from ctypes import wintypes

        fn = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        fn.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        fn.restype = wintypes.BOOL
        return 0 if fn(src, dst, flags) else int(ctypes.get_last_error())

    code, failed = attempt(call, (OSError, AttributeError, ImportError, TypeError, ValueError))
    if failed is not None or code is None:
        raise OSError("MoveFileExW is unavailable")
    return code


def _publish_win32(tmp: str, final: str) -> PublishFailure | None:
    """Durable no-clobber publish: write-through, and no fallback to a non-durable path."""

    def move() -> int:
        code = 0
        for tries in range(BUSY_RETRIES + 1):
            code = _move_file_ex(tmp, final, MOVEFILE_WRITE_THROUGH)
            if code not in BUSY_CODES or tries == BUSY_RETRIES:
                break
            time.sleep(BUSY_BACKOFF_SECONDS)
        return code

    code, failed = attempt(move, (OSError,))
    if failed is not None or code is None:
        return PublishFailure("unsafe")
    if code == 0:
        return None
    kind: Literal["exists", "busy", "unsafe"] = (
        "exists" if code in EXISTS_CODES else "busy" if code in BUSY_CODES else "unsafe"
    )
    return PublishFailure(kind, code)


def _publish_posix(tmp: str, final: str) -> PublishFailure | None:  # pragma: no cover
    """POSIX only, unverified here: os.link never overwrites; then fsync the folder entry."""
    _, linked = attempt(lambda: os.link(tmp, final), (OSError,))
    if linked is not None:
        exists = issubclass(linked[0], FileExistsError)
        return PublishFailure("exists" if exists else "unsafe", linked[1])
    _quiet_unlink(tmp)

    def sync_dir() -> None:
        fd = os.open(os.path.dirname(final), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    _, failed = attempt(sync_dir, (OSError,))
    return None if failed is None else PublishFailure("unsafe", failed[1])


def publish(tmp: str, final: str) -> PublishFailure | None:
    return _publish_win32(tmp, final) if sys.platform == "win32" else _publish_posix(tmp, final)


def _quiet_unlink(path: str | None) -> None:
    if path is not None:
        attempt(lambda: os.unlink(path), (OSError,))  # a stray .tmp-* is harmless


def _try_lock(fd: int) -> None:
    """Non-blocking exclusive lock on byte 0; OSError means another process holds it."""
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:  # pragma: no cover - POSIX only, unverified here
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(fd: int) -> None:
    if sys.platform == "win32":
        import msvcrt

        def release() -> None:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

        attempt(release, (OSError,))
    os.close(fd)  # on POSIX closing the descriptor releases the flock


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def stage(run_dir: str | os.PathLike[str], data: bytes) -> str:
    """Create .tmp-*, write all bytes, fsync. On any failure the temp file is removed."""
    fd, tmp = tempfile.mkstemp(dir=run_dir, prefix=".tmp-", suffix=".json")
    done = False
    try:
        try:
            _write_all(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        done = True
    finally:
        if not done:
            _quiet_unlink(tmp)
    return tmp
