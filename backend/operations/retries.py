"""Retry timing shared by receipt processing, provider reads, and issue creation."""

import random
from datetime import datetime, timedelta

MAX_ATTEMPTS = 12
# Backoff stops doubling at 2**10 = 1024 seconds.
MAX_BACKOFF_DOUBLINGS = 10


def next_retry_at(*, now: datetime, attempts: int, retry_after: int | None = None) -> datetime:
    delay = (
        max(0, retry_after)
        if retry_after is not None
        else 2 ** min(attempts, MAX_BACKOFF_DOUBLINGS)
    )
    return now + timedelta(seconds=delay + random.randint(0, max(1, min(delay // 4, 60))))
