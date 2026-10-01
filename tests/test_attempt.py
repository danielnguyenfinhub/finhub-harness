"""Slice 6 delta to slice 5: ``_fsio.attempt`` is total and never reads a hostile instance (T23).

Synthetic data only. The marker below must never reach stderr or an outcome.
"""

from __future__ import annotations

import sys
import time
from typing import Any

import pytest

from master_finhub.orchestration._fsio import attempt

MARKER = "MARKERclientA"


class _ErrnoBomb(OSError):
    @property  # type: ignore[override]
    def errno(self) -> int:
        raise RuntimeError(MARKER)

    def __str__(self) -> str:
        raise RuntimeError(MARKER)

    def __repr__(self) -> str:
        raise RuntimeError(MARKER)


class _ClassBomb(Exception):
    @property  # type: ignore[override]
    def __class__(self) -> type:  # type: ignore[override]
        raise RuntimeError(MARKER)


class _Custom(BaseException):
    @property
    def errno(self) -> int:
        raise RuntimeError(MARKER)


def _raiser(exc: BaseException) -> Any:
    def go() -> None:
        raise exc

    return go


def test_attempt_total_on_hostile_errno_property(capfd: pytest.CaptureFixture[str]) -> None:
    start = time.monotonic()
    value, failure = attempt(_raiser(_ErrnoBomb(5, "x")), (OSError,))
    assert value is None
    assert failure == (_ErrnoBomb, 5)  # the base slot, not the raising property
    assert time.monotonic() - start < 1.0
    assert capfd.readouterr().err == ""


def test_attempt_string_errno_is_zero() -> None:
    assert attempt(_raiser(OSError(MARKER, "x")), (OSError,))[1] == (OSError, 0)


def test_attempt_real_errno_survives() -> None:
    err = PermissionError(13, "denied", "C:/x")
    assert attempt(_raiser(err), (OSError,))[1] == (PermissionError, 13)


@pytest.mark.parametrize("bad", [True, 2**5000, -1], ids=["bool", "huge", "negative"])
def test_attempt_bool_huge_negative_errno_is_zero(bad: Any) -> None:
    failure = attempt(_raiser(OSError(bad, "x")), (OSError,))[1]
    assert failure is not None and failure[1] == 0  # class may map from errno; errno must not


def test_attempt_int_subclass_errno_is_zero() -> None:
    class Evil(int):
        def __int__(self) -> int:
            raise RuntimeError(MARKER)

    failure = attempt(_raiser(OSError(Evil(7), "x")), (OSError,))[1]
    assert failure is not None and failure[1] == 0


def test_attempt_class_property_bomb_and_base_exception_subclass() -> None:
    assert attempt(_raiser(_ClassBomb(MARKER)), (Exception,))[1] == (_ClassBomb, 0)
    assert attempt(_raiser(_Custom(MARKER)), (BaseException,))[1] == (_Custom, 0)


def test_attempt_never_stringifies_instance(capfd: pytest.CaptureFixture[str]) -> None:
    for exc in (_ErrnoBomb(5, "x"), _ClassBomb(MARKER), _Custom(MARKER)):
        value, failure = attempt(_raiser(exc), (BaseException,))
        assert value is None and failure is not None
        assert MARKER not in repr(failure)
    captured = capfd.readouterr()
    assert MARKER not in captured.err and MARKER not in captured.out
    assert sys.exc_info() == (None, None, None)


def test_attempt_passes_uncaught_through() -> None:
    with pytest.raises(KeyError):
        attempt(_raiser(KeyError("k")), (ValueError,))
