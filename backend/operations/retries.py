"""Retry timing shared by receipt processing and provider reads."""

import random
from datetime import datetime, timedelta

MAX_ATTEMPTS = 12


def next_retry_at(*, now: datetime, attempts: int, retry_after: int | None = None) -> datetime:
    delay = max(0, retry_after) if retry_after is not None else min(3600, 2 ** min(attempts, 10))
    return now + timedelta(seconds=delay + random.randint(0, max(1, min(delay // 4, 60))))
