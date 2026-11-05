"""Proof for the stall detector (HV1): bigram similarity, windowed stall check, silence clock.

adapted from references/hive/core/framework/agent_loop/internals/stall_detector.py:11 (Apache-2.0)
"""

from master_finhub.runtime.stall import (
    SILENCE_AT,
    bigram_similarity,
    is_stalled,
    silence_level,
)

A = "I am still stuck on the signature page and cannot continue."
B = "I'm still stuck on the signature page, I cannot continue."
C = "Done. The document pack is complete and lodged for review."


def test_identical_text_scores_one_and_empty_scores_zero() -> None:
    assert bigram_similarity(A, A) == 1.0
    assert bigram_similarity("", A) == 0.0
    assert bigram_similarity(A, "") == 0.0


def test_single_character_text_is_compared_by_equality() -> None:
    assert bigram_similarity("a", "a") == 1.0
    assert bigram_similarity("a", "b") == 0.0


def test_rephrased_replies_score_high_and_unrelated_low() -> None:
    assert bigram_similarity(A, B) > 0.7
    assert bigram_similarity(A, C) < 0.4


def test_case_is_ignored() -> None:
    assert bigram_similarity("HELLO THERE", "hello there") == 1.0


def test_rephrased_replies_flag_stalled() -> None:
    assert is_stalled([A, B, A], window=3, threshold=0.7) is True


def test_one_dissimilar_reply_resets_the_signal() -> None:
    assert is_stalled([A, B, C], window=3, threshold=0.7) is False
    assert is_stalled([A, C, B], window=3, threshold=0.7) is False


def test_fewer_replies_than_the_window_is_not_stalled() -> None:
    assert is_stalled([A, B], window=3, threshold=0.7) is False


def test_only_the_last_window_replies_count() -> None:
    assert is_stalled([C, A, B, A], window=3, threshold=0.7) is True


def test_empty_first_reply_is_not_stalled() -> None:
    assert is_stalled(["", "", ""], window=3, threshold=0.7) is False


def test_attempt_numbers_do_not_make_a_stall() -> None:
    assert is_stalled(["attempt 1 failed", "attempt 2 failed", "attempt 3 failed"], 3, 0.9) is False


def test_window_below_two_is_refused() -> None:
    import pytest

    with pytest.raises(ValueError):
        is_stalled([A, A], window=1, threshold=0.7)


def test_silence_levels_at_fixed_now_values() -> None:
    first, second, third = SILENCE_AT
    t0 = 1000.0
    assert silence_level(t0, t0 + first - 1) == 0
    assert silence_level(t0, t0 + first) == 1
    assert silence_level(t0, t0 + second) == 2
    assert silence_level(t0, t0 + third + 500) == 3


def test_clock_going_backwards_is_level_zero() -> None:
    assert silence_level(1000.0, 900.0) == 0


def test_a_score_equal_to_the_threshold_counts_as_similar() -> None:
    assert is_stalled([A, A, A], window=3, threshold=1.0) is True
