"""Unit tests for the in-memory RateLimiter."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from fpl_agent.middleware.rate_limit import RateLimiter

pytestmark = pytest.mark.unit


def test_first_n_requests_pass() -> None:
    limiter = RateLimiter(per_min=5, per_hour=20)
    for _ in range(5):
        allowed, retry = limiter.allow("session-A")
        assert allowed is True
        assert retry is None


def test_minute_limit_triggers_429() -> None:
    limiter = RateLimiter(per_min=3, per_hour=20)
    for _ in range(3):
        limiter.allow("session-A")
    allowed, retry = limiter.allow("session-A")
    assert allowed is False
    assert retry is not None
    assert 0 < retry <= 60


def test_separate_sessions_independent() -> None:
    limiter = RateLimiter(per_min=2, per_hour=10)
    limiter.allow("A")
    limiter.allow("A")
    # A is full, B should still have its full budget.
    allowed_b, _ = limiter.allow("B")
    assert allowed_b is True
    allowed_a, _ = limiter.allow("A")
    assert allowed_a is False


def test_minute_window_slides() -> None:
    """After the minute window rolls past the oldest request, new ones pass."""
    limiter = RateLimiter(per_min=2, per_hour=100)
    fake_clock = [1000.0]

    def now() -> float:
        return fake_clock[0]

    with patch.object(time, "monotonic", side_effect=lambda: now()):
        assert limiter.allow("S")[0] is True  # t=1000
        assert limiter.allow("S")[0] is True  # t=1000
        assert limiter.allow("S")[0] is False  # t=1000 — minute full

        fake_clock[0] = 1061.0  # advance 61 seconds
        assert limiter.allow("S")[0] is True  # oldest evicted


def test_hour_limit_blocks_even_if_minute_ok() -> None:
    """Patient caller can't drain by pacing per-minute."""
    limiter = RateLimiter(per_min=10, per_hour=3)
    fake_clock = [1000.0]

    with patch.object(time, "monotonic", side_effect=lambda: fake_clock[0]):
        for _ in range(3):
            fake_clock[0] += 61  # slide past minute window each time
            allowed, _ = limiter.allow("S")
            assert allowed is True
        fake_clock[0] += 61
        allowed, retry = limiter.allow("S")
        assert allowed is False
        assert retry is not None
