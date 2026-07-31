"""Small in-process guard for bursty authenticated mutations.

This is intentionally conservative and bounded; deploy-wide throttling should
eventually live at the edge or in Redis.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, status

_events: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def check_rate_limit(key: str, *, limit: int, window_seconds: float = 60.0) -> None:
    now = monotonic()
    with _lock:
        bucket = _events[key]
        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests; try again shortly",
                    }
                },
            )
        bucket.append(now)
