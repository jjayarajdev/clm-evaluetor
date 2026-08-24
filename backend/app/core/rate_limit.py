"""In-memory sliding-window rate limiting for abuse-prone endpoints.

Scope: brute-force protection on auth and cost protection on uploads (every
upload triggers paid LLM calls). The store is per-process — with N uvicorn
workers a client can get up to N× the nominal limit — which is the right
trade-off for a single-box deployment with no Redis: limits here are abuse
ceilings, not precise quotas. Set the nominal values with that in mind.

Keying: per client IP (first X-Forwarded-For entry when present) or, for
authenticated endpoints, per user id — the latter can't be spoofed by a
client that reaches the backend port directly and forges XFF.
"""

import math
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

from app.config import settings
from app.core.middleware import _get_client_ip


class SlidingWindowLimiter:
    """Sliding-window counter: at most `times` hits per `seconds` per key."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, times: int, seconds: float) -> float | None:
        """Record a hit for `key`.

        Returns None if allowed, or the seconds to wait if over the limit
        (the hit is not recorded in that case, so waiting actually helps).
        """
        now = time.monotonic()
        window = self._hits[key]
        cutoff = now - seconds
        while window and window[0] <= cutoff:
            window.popleft()
        if not window:
            # Fully-expired keys would otherwise accumulate forever.
            del self._hits[key]
            window = self._hits[key]
        if len(window) >= times:
            return window[0] + seconds - now
        window.append(now)
        return None

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindowLimiter()


def _reject(retry_after: float) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests — please try again shortly",
        headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
    )


def rate_limit_by_ip(scope: str, times: int, seconds: float = 60.0):
    """Dependency: limit unauthenticated requests per client IP."""

    async def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        ip = _get_client_ip(request) or "unknown"
        retry_after = limiter.check(f"{scope}:{ip}", times, seconds)
        if retry_after is not None:
            _reject(retry_after)

    return dependency


def rate_limit_by_user(scope: str, times: int, seconds: float = 60.0):
    """Dependency: limit authenticated requests per user id.

    Runs after auth (imports get_current_user lazily to avoid a module
    cycle), so unauthenticated requests fail with 401 before counting.
    """
    from app.core.deps import get_current_user

    async def dependency(current_user=Depends(get_current_user)) -> None:
        if not settings.rate_limit_enabled:
            return
        retry_after = limiter.check(
            f"{scope}:{current_user.id}", times, seconds
        )
        if retry_after is not None:
            _reject(retry_after)

    return dependency
