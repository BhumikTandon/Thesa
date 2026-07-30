"""HTTP security middleware: response headers and tiered rate limiting.

Implements the controls from DOCUMENTATION.md § Security Standard (§5–6)
without external dependencies. The rate limiter is an in-process sliding
window — sufficient for a single API instance; swap the store for Redis when
running replicas so limits hold across processes.
"""

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every response.

    Authenticated responses additionally get `Cache-Control: no-store` so
    tenant data is never cached by intermediaries or browsers.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if request.headers.get("Authorization"):
            response.headers["Cache-Control"] = "no-store"
        return response


# Requests per 60-second sliding window.
ANON_IP_LIMIT = 300
USER_LIMIT = 60
SENSITIVE_LIMIT = 30

_WINDOW_SECONDS = 60.0

# State-changing operations on money-adjacent resources get the tight limit.
_SENSITIVE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
_SENSITIVE_PREFIXES = (
    "/portfolio-cards",
    "/budgets",
    "/per-diems",
    "/routing",
    "/team",
)


class _SlidingWindow:
    """Per-key sliding window counters. In-process only."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, now: float) -> tuple[bool, float]:
        """Record a hit; return (allowed, seconds until a slot frees up)."""
        window = self._hits[key]
        cutoff = now - _WINDOW_SECONDS
        while window and window[0] <= cutoff:
            window.popleft()
        if len(window) >= limit:
            return False, max(0.0, window[0] + _WINDOW_SECONDS - now)
        window.append(now)
        return True, 0.0

    def prune(self, now: float) -> None:
        cutoff = now - _WINDOW_SECONDS
        stale = [k for k, w in self._hits.items() if not w or w[-1] <= cutoff]
        for k in stale:
            del self._hits[k]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Tiered rate limiting (runs after auth, so identity is available).

    - Authenticated: per-user limit, tighter on sensitive write endpoints.
    - Unauthenticated / public: per-IP limit.
    Responses over the limit get 429 with Retry-After.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._window = _SlidingWindow()
        self._last_prune = 0.0

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        now = time.monotonic()
        if now - self._last_prune > _WINDOW_SECONDS:
            self._window.prune(now)
            self._last_prune = now

        clerk_user_id = getattr(request.state, "clerk_user_id", None)
        if clerk_user_id:
            key = f"user:{clerk_user_id}"
            limit = USER_LIMIT
            if request.method in _SENSITIVE_METHODS and request.url.path.startswith(
                _SENSITIVE_PREFIXES
            ):
                key = f"user-sensitive:{clerk_user_id}"
                limit = SENSITIVE_LIMIT
        else:
            client_ip = request.client.host if request.client else "unknown"
            key = f"ip:{client_ip}"
            limit = ANON_IP_LIMIT

        allowed, retry_after = self._window.check(key, limit, now)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(max(1, int(retry_after) + 1))},
            )

        return await call_next(request)
