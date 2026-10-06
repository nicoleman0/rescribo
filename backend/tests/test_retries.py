"""Unit tests for shared retry timing."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from operations.retries import next_retry_at

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)


def delay(*, attempts: int, retry_after: int | None = None) -> int:
    due = next_retry_at(now=NOW, attempts=attempts, retry_after=retry_after)
    return int((due - NOW) / timedelta(seconds=1))


@pytest.mark.parametrize(("attempts", "base"), [(0, 1), (1, 2), (4, 16), (10, 1024)])
def test_backoff_doubles_per_attempt(attempts: int, base: int) -> None:
    with patch("operations.retries.random.randint", return_value=0):
        assert delay(attempts=attempts) == base


@pytest.mark.parametrize("attempts", [12, 20, 1000])
def test_backoff_stops_growing_after_ten_attempts(attempts: int) -> None:
    with patch("operations.retries.random.randint", return_value=0):
        assert delay(attempts=attempts) == 1024


def test_retry_after_replaces_backoff_and_is_a_floor() -> None:
    for _ in range(50):
        assert 120 <= delay(attempts=9, retry_after=120) <= 150


def test_zero_retry_after_still_adds_jitter() -> None:
    with patch("operations.retries.random.randint", return_value=1) as jitter:
        assert delay(attempts=5, retry_after=0) == 1
    jitter.assert_called_once_with(0, 1)


def test_negative_retry_after_is_treated_as_zero() -> None:
    assert 0 <= delay(attempts=5, retry_after=-30) <= 1


@pytest.mark.parametrize(("attempts", "retry_after", "bound"), [(4, None, 4), (10, None, 60)])
def test_jitter_is_a_quarter_of_the_delay_up_to_a_minute(
    attempts: int, retry_after: int | None, bound: int
) -> None:
    with patch("operations.retries.random.randint", return_value=0) as jitter:
        delay(attempts=attempts, retry_after=retry_after)
    jitter.assert_called_once_with(0, bound)
