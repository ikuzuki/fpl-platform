"""In-memory sliding-window rate limiter keyed by session id.

**Caveat.** State is held in a Python dict on the Lambda container. Two
warm containers can therefore each grant the full per-minute budget, so
the *effective* rate is up to ``per_min × N_containers``. That's good
enough for dev / demo-level abuse protection — a real ceiling needs
Redis, DynamoDB, or an API Gateway usage plan. Flagged as a follow-up
in PR #92's body.

The sliding window is implemented with a ``deque`` per session: timestamps
older than the window are popped on each call. This is O(1) amortised
and avoids the classic fixed-window edge case where a user can burst
``2*limit`` by straddling the window boundary.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window limiter with both per-minute and per-hour budgets.

    The per-hour budget stops a patient caller from hitting the per-minute
    limit on a 60-second cadence and draining hundreds of Sonnet calls in
    a day. Both windows share one deque per session — checking both costs
    two ``len`` reads.
    """

    def __init__(self, per_min: int = 5, per_hour: int = 20) -> None:
        self._per_min = per_min
        self._per_hour = per_hour
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, session_id: str) -> tuple[bool, int | None]:
        """Record a request attempt and return ``(allowed, retry_after_sec)``.

        ``retry_after_sec`` is the number of seconds the caller should
        wait before retrying. Returned only when ``allowed`` is False.
        """
        now = time.monotonic()
        minute_cutoff = now - 60
        hour_cutoff = now - 3600

        with self._lock:
            window = self._windows[session_id]
            # Evict anything older than the hour window — the minute window
            # is a strict subset, so this cleans up for both checks.
            while window and window[0] < hour_cutoff:
                window.popleft()

            in_last_minute = sum(1 for t in window if t >= minute_cutoff)
            in_last_hour = len(window)

            if in_last_minute >= self._per_min:
                oldest_in_minute = next(t for t in window if t >= minute_cutoff)
                retry_after = max(1, int(60 - (now - oldest_in_minute)))
                return False, retry_after
            if in_last_hour >= self._per_hour:
                retry_after = max(1, int(3600 - (now - window[0])))
                return False, retry_after

            window.append(now)
            return True, None
